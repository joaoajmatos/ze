"""eval/calibration/routing.py works offline: fake embedder, fake client, no credits."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from ze_agents.registry import clear_registry
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from tests.support.routing import cosine_embedder, register_agent

_SCRIPT = Path(__file__).resolve().parents[5] / "eval/calibration/routing.py"


@pytest.fixture(scope="module")
def calib():
    spec = importlib.util.spec_from_file_location("routing_calibration", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


class _OracleClient:
    """Answers from the gold labels carried in the state's user text."""

    def __init__(self, gold):
        self.gold = gold
        self.orders: list[list[str]] = []

    async def evaluate(self, state, questions, *, max_attempts=None):
        assert max_attempts == 1
        agent_q = questions["agent"]
        self.orders.append(list(agent_q.criteria))
        row = self.gold[state["user"]]
        choice = row.gold_agent if row.gold_agent in agent_q.criteria else "none"
        return SystemOneResult(
            outcome="ok",
            model="oracle",
            answers={
                "agent": SystemOneAnswer(
                    type="choice",
                    choice=choice,
                    confidence=0.92,
                    probabilities={choice: 0.92},
                ),
                "multi_specialist": SystemOneAnswer(
                    type="noul", noul=0.9 if row.gold_multi else 0.05
                ),
            },
        )


async def _run_rows(calib, client, embedder, roster, rows, *, seed, concurrency, k):
    prepared = calib.prepare(embedder, roster, roster, rows, seed=seed, k=k)
    results = await calib.harness.run_live(
        client,
        rows,
        lambda row: prepared[row.id][4],
        lambda _, row: prepared[row.id][5],
        concurrency,
    )
    return [
        calib.Outcome(row, names, top, gap, results[row.id])
        for row, names, top, gap, _, _ in prepared.values()
    ]


def _roster() -> dict[str, str]:
    clear_registry()
    names = ["calendar", "messenger", "research", "reminders", "companion"]
    for n in names:
        register_agent(n)
    return {n: f"The {n} agent" for n in names}


async def test_offline_run_reports_and_suggests(calib, capsys):
    roster = _roster()
    rows = calib.load_rows(calib.DATASET)
    gold = {r.prompt: r for r in rows}
    client = _OracleClient(gold)
    # Every agent's cosine is a fixed close band so 160 alone would decompose.
    embedder = cosine_embedder(
        {n: 0.80 - 0.001 * i for i, n in enumerate(sorted(roster))}
    )

    outcomes = await _run_rows(
        calib, client, embedder, roster, rows, seed=164, concurrency=4, k=3
    )
    suggestion = calib.report(outcomes)
    out = capsys.readouterr().out

    assert len(outcomes) == len(rows)
    assert all(len(o.names) == 3 for o in outcomes)
    assert "Choice accuracy" in out and "multiple-specialist Noul" in out
    assert "complexity" not in out
    assert "complexity_lookup_max" not in suggestion
    assert suggestion["choice_trust"] is not None
    assert suggestion["multi_specialist_hold"] is not None


async def test_option_order_is_shuffled_per_row(calib):
    roster = _roster()
    rows = calib.load_rows(calib.DATASET)
    client = _OracleClient({r.prompt: r for r in rows})
    embedder = cosine_embedder(
        {n: 0.8 - 0.01 * i for i, n in enumerate(sorted(roster))}
    )
    await _run_rows(calib, client, embedder, roster, rows, seed=1, concurrency=4, k=4)
    shortlist_orders = {tuple(o[:-1]) for o in client.orders}
    assert len(shortlist_orders) > 1
    assert all(o[-1] == "none" for o in client.orders)


def test_shortlist_recall_counts_gold_outside_top_k(calib):
    roster = _roster()
    rows = [
        calib.Row("a", "en", "x", "calendar", False, None),
        calib.Row("b", "en", "y", "research", False, None),
    ]
    embedder = cosine_embedder({"calendar": 0.9, "research": 0.1, "messenger": 0.5})
    misses = calib.shortlist_recall(embedder, roster, rows, (2, 5))
    assert [r.id for r in misses[2]] == ["b"]
    assert len(misses[5]) <= len(misses[2])


def test_grid_counts_harm_when_trusting_the_wrong_agent(calib):
    roster = _roster()
    row = calib.Row("r", "en", "p", "calendar", False)
    result = SystemOneResult(
        outcome="ok",
        answers={
            "agent": SystemOneAnswer(
                type="choice", choice="messenger", confidence=0.95, probabilities={}
            ),
            "multi_specialist": SystemOneAnswer(type="noul", noul=0.0),
        },
    )
    outcome = calib.Outcome(row, ["calendar", "messenger"], 0.8, 0.0, result)
    metrics = calib.grid_metrics([outcome])
    assert all(m["harmful"] == 1 for m in metrics if m["trust"] <= 0.9)
    assert all(m["removed"] == 0 for m in metrics)
    assert roster


def test_recall_sweep_runs_to_roster_size_and_finds_smallest_passing_k(calib, capsys):
    roster = _roster()
    rows = [
        calib.Row("a", "en", "x", "calendar", False, None),
        calib.Row("b", "en", "y", "research", False, None),
    ]
    embedder = cosine_embedder(
        {
            "calendar": 0.9,
            "research": 0.1,
            "messenger": 0.5,
            "reminders": 0.4,
            "companion": 0.3,
        }
    )
    best = calib.report_recall(embedder, roster, {"one": rows, "two": rows[:1]})
    out = capsys.readouterr().out

    assert calib.recall_ks(roster) == (2, 3, 4, 5)
    assert "== one" in out and "== two" in out
    assert best is not None and best <= len(roster)
    assert f"Smallest k with recall >= 0.95 on every set: {best}" in out


def test_smallest_passing_k_is_none_when_a_set_never_passes(calib):
    assert calib.smallest_passing_k([{2: 1.0, 3: 1.0}, {2: 0.5, 3: 0.9}]) is None
    assert calib.smallest_passing_k([{2: 0.9, 3: 1.0}, {2: 1.0, 3: 1.0}]) == 3


def _outcome(calib, rid, lang, gold, pred, conf):
    row = calib.Row(rid, lang, "p", gold, False)
    result = SystemOneResult(
        outcome="ok",
        answers={
            "agent": SystemOneAnswer(
                type="choice", choice=pred, confidence=conf, probabilities={}
            )
        },
    )
    return calib.Outcome(row, [gold, pred], 0.8, 0.0, result)


def test_verdict_passes_a_clean_set_and_prints_per_language(calib, capsys):
    outcomes = [
        _outcome(calib, f"{lang}{i}", lang, "research", "research", 0.97)
        for lang in ("en", "pt")
        for i in range(20)
    ]
    verdicts = calib.report_verdicts({"clean": outcomes})
    out = capsys.readouterr().out
    assert verdicts[0].passed
    assert "[en] accuracy 20/20" in out and "[pt] accuracy 20/20" in out
    assert "OVERALL: PASS" in out


def test_verdict_gates_on_trusted_research_to_companion_misses(calib):
    outcomes = [
        _outcome(calib, f"en{i}", "en", "research", "research", 0.97) for i in range(40)
    ]
    outcomes.append(_outcome(calib, "enx", "en", "research", "companion", 0.9))
    verdict = calib.verdict_for_set("held", outcomes)
    assert calib.research_to_companion_misses(outcomes, 0.95) == 0
    assert verdict.passed
    assert any(
        "lowest choice_trust with zero trusted misses: 0.95" in x for x in verdict.lines
    )
    outcomes.append(_outcome(calib, "eny", "en", "research", "companion", 1.0))
    verdict = calib.verdict_for_set("held", outcomes)
    assert not verdict.passed
    assert calib.research_to_companion_misses(outcomes, 0.85) == 2


def test_verdict_fails_below_accuracy_bar_or_above_ece(calib):
    outcomes = [
        _outcome(calib, f"en{i}", "en", "calendar", "calendar", 0.97) for i in range(5)
    ] + [
        _outcome(calib, f"enm{i}", "en", "calendar", "messenger", 0.97)
        for i in range(5)
    ]
    verdict = calib.verdict_for_set("held", outcomes)
    assert not verdict.passed
    assert any(line.startswith("FAIL") and "accuracy" in line for line in verdict.lines)
    assert any(line.startswith("FAIL") and "ECE" in line for line in verdict.lines)


def test_load_roster_returns_descriptions_and_criteria(calib):
    descriptions, criteria = calib.load_roster()
    assert set(descriptions) == set(criteria)
    assert "explain X" not in descriptions["companion"]
    assert criteria["research"] != descriptions["research"]


def test_check_sets_passes_on_the_shipped_sets_and_prints_counts_only(calib, capsys):
    assert calib.check_sets() == 0
    out = capsys.readouterr().out
    assert "routing_screen" in out and "en=" in out and "pt=" in out
    assert "summarize this" not in out


def test_check_sets_reports_schema_problems(calib, tmp_path, capsys):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"id": "a", "lang": "xx", "prompt": "p", "gold_agent": "x", "gold_multi": 1, "mystery": 1}\n'
        '{"id": "a", "lang": "en", "prompt": "p", "gold_agent": "x", "gold_multi": false, "screen": " "}\n',
        encoding="utf-8",
    )
    assert calib.check_sets((bad,)) == 1
    err = capsys.readouterr().err
    assert "lang must be" in err and "gold_multi" in err
    assert "unknown keys" in err and "duplicate id" in err and "screen must be" in err


def test_screen_column_is_appended_to_context_like_production(calib):
    from ze_core.orchestration.judgment_state import build_judgment_state

    row = calib.load_rows(_SCRIPT.with_name("routing_screen.jsonl"))[0]
    assert row.screen
    prod = build_judgment_state(
        {"prompt": row.prompt, "routing_hints": None}, row.screen
    )
    ours = calib.build_state(
        row.prompt, None, calib.with_screen_line(None, row.screen)
    )
    assert ours["context"] == prod["context"] == row.screen


def test_calibrate_routing_recipe_forwards_args():
    makefile = (_SCRIPT.parents[2] / "Makefile").read_text(encoding="utf-8")
    recipe = makefile.split("\ncalibrate-routing:\n", 1)[1].split("\n\n", 1)[0]
    assert "$(ARGS)" in recipe
