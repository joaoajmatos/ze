"""Offline tests for the commitment-intake calibration tooling (T040, T041). No network."""

import importlib.util
import sys
from pathlib import Path

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

CAL_DIR = Path(__file__).resolve().parents[4] / "eval" / "calibration"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, CAL_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cal():
    return _load("commitment_intake_cal_scoring", "commitment_intake.py")


@pytest.fixture(scope="module")
def baseline():
    return _load("commitment_intake_baseline_mod", "commitment_intake_baseline.py")


def _noul(v):
    return SystemOneAnswer(type="noul", noul=v)


def _choice(label, conf=0.95):
    return SystemOneAnswer(type="choice", choice=label, confidence=conf)


def _system(
    commitment, *, concern=0.05, explicit=0.05, resolves=0.05, bio=0.05, family="drop"
):
    return SystemOneResult(
        outcome="ok",
        answers={
            "commitment": _choice(commitment),
            "family": _choice(family),
            "biography": _noul(bio),
            "is_open_concern": _noul(concern),
            "explicit_declaration": _noul(explicit),
            "resolves_existing": _noul(resolves),
        },
    )


def _r163(act, *, bio=0.05, family="drop"):
    return SystemOneResult(
        outcome="ok",
        answers={
            "speech_act": _choice(act),
            "family": _choice(family),
            "biography": _noul(bio),
        },
    )


def _r168(concern=0.05, explicit=0.05, resolves=0.05):
    return SystemOneResult(
        outcome="ok",
        answers={
            "is_open_concern": _noul(concern),
            "explicit_declaration": _noul(explicit),
            "resolves_existing": _noul(resolves),
        },
    )


def _row(cal, **over):
    base = dict(
        id="x",
        lang="en",
        text="t",
        assistant="a",
        gold_choice="none",
        gold_explicit=False,
        gold_resolves=False,
        turn_created="none",
        kind="none_question",
    )
    base.update(over)
    return cal.Row(**base)


def _bars(cal):
    return cal.make_cfg(0.7, 0.7, 0.7, 0.75, 0.85, 0.8)


def test_duplicate_booking_is_a_loop_where_the_turn_created_a_reminder(cal):
    row = _row(cal, id="d", gold_choice="loop", turn_created="reminder")
    results = {
        "d": cal.RowResults(
            _system("loop", concern=0.95, explicit=0.9),
            _r163("reminder"),
            _r168(concern=0.95, explicit=0.9),
        )
    }
    system = cal.score([row], cal.preds_for([row], results, _bars(cal)))
    base = cal.score([row], cal.baseline_preds([row], results))
    assert system.duplicates == 0 and system.false_creates == 0
    assert base.duplicates == 1


def test_false_create_on_a_negative_row_and_loop_hit(cal):
    neg = _row(cal, id="n", gold_choice="none")
    pos = _row(cal, id="p", gold_choice="loop", gold_explicit=True)
    results = {
        "n": cal.RowResults(_system("loop", concern=0.9), _r163("drop"), _r168()),
        "p": cal.RowResults(
            _system("loop", concern=0.9, explicit=0.9),
            _r163("drop"),
            _r168(concern=0.9, explicit=0.9),
        ),
    }
    c = cal.score([neg, pos], cal.preds_for([neg, pos], results, _bars(cal)))
    assert c.false_creates == 1
    assert c.loop_hits == 1 and c.loop_pos == 1
    assert c.loop_precision == 0.5
    assert c.explicit_acc == 1.0


def test_waiting_on_row_written_to_a_store_is_counted(cal):
    row = _row(cal, id="w", gold_choice="waiting_on", kind="waiting_on")
    held = {"w": cal.RowResults(_system("waiting_on"), _r163("drop"), _r168())}
    written = {
        "w": cal.RowResults(_system("loop", concern=0.9), _r163("drop"), _r168())
    }
    assert cal.score([row], cal.preds_for([row], held, _bars(cal))).waiting_written == 0
    assert (
        cal.score([row], cal.preds_for([row], written, _bars(cal))).waiting_written == 1
    )


def test_fact_precision_and_recall_against_the_163_baseline(cal):
    fact = _row(cal, id="f", gold_choice="fact", gold_family="preference")
    results = {
        "f": cal.RowResults(
            _system("fact", bio=0.9, family="preference"),
            _r163("fact", bio=0.9, family="preference"),
            _r168(),
        )
    }
    system = cal.score([fact], cal.preds_for([fact], results, _bars(cal)))
    base = cal.score([fact], cal.baseline_preds([fact], results))
    assert (system.fact_hits, base.fact_hits) == (1, 1)
    assert system.fact_precision == base.fact_precision == 1.0


def test_choice_accuracy_counts_skipped_requests_as_wrong(cal):
    row = _row(cal, id="s", gold_choice="none")
    skipped = SystemOneResult(outcome="skip", skip_reason="timeout")
    results = {"s": cal.RowResults(skipped, _r163("drop"), _r168())}
    chosen = cal.choices_for([row], results)
    c = cal.score([row], cal.preds_for([row], results, _bars(cal)), chosen)
    assert chosen["s"] is None
    assert c.choice_ok == 0 and c.choice_total == 1
    assert c.fallback == 1


def test_verdict_names_every_failing_clause(cal):
    system = cal.Counts(
        duplicates=1,
        false_creates=1,
        fact_pos=10,
        fact_pred=10,
        fact_hits=5,
        loop_pos=10,
        loop_pred=10,
        loop_hits=5,
        choice_total=10,
        choice_ok=5,
    )
    baseline = cal.Counts(
        fact_pos=10, fact_pred=10, fact_hits=10, loop_pos=10, loop_pred=10, loop_hits=10
    )
    ok, failing = cal.verdict(system, baseline)
    assert not ok
    joined = " | ".join(failing)
    for clause in (
        "duplicate bookings",
        "false loop creates",
        "fact precision",
        "fact recall",
        "loop precision",
        "loop recall",
        "Choice accuracy",
    ):
        assert clause in joined


def test_verdict_passes_when_every_clause_holds(cal):
    good = cal.Counts(
        fact_pos=10,
        fact_pred=10,
        fact_hits=10,
        loop_pos=10,
        loop_pred=10,
        loop_hits=10,
        choice_total=10,
        choice_ok=10,
    )
    ok, failing = cal.verdict(good, good)
    assert ok and failing == []


def test_suggest_bars_returns_a_complete_config_or_none(cal):
    rows = [
        _row(cal, id="f", gold_choice="fact", gold_family="preference"),
        _row(cal, id="l", gold_choice="loop", gold_explicit=True),
        _row(cal, id="n"),
    ]
    results = {
        "f": cal.RowResults(
            _system("fact", bio=0.9, family="preference"), _r163("fact"), _r168()
        ),
        "l": cal.RowResults(
            _system("loop", concern=0.9, explicit=0.9), _r163("drop"), _r168()
        ),
        "n": cal.RowResults(_system("none"), _r163("drop"), _r168()),
    }
    cfg = cal.suggest_bars(rows, results)
    assert cfg is not None and cfg.calibrated
    preds = cal.preds_for(rows, results, cfg)
    assert preds["f"].fact and preds["l"].declared and not preds["n"].create


def test_saved_results_round_trip(cal, tmp_path):
    results = {
        "a": cal.RowResults(_system("loop", concern=0.8), _r163("loop"), _r168())
    }
    path = tmp_path / "r.json"
    cal.save_results(path, results)
    back = cal.load_results(path)
    assert back["a"].system.answers["commitment"].choice == "loop"
    assert back["a"].r168.answers["is_open_concern"].noul == 0.05


class _CountingClient:
    def __init__(self):
        self.calls = []

    async def evaluate(self, state, questions, *, max_attempts=None):
        self.calls.append((sorted(questions), max_attempts))
        return SystemOneResult(outcome="skip", skip_reason="disabled")


async def test_run_rows_makes_one_intake_request_and_two_baseline_requests(cal):
    client = _CountingClient()
    rows = [_row(cal, id="a"), _row(cal, id="b")]
    results = await cal.run_rows(client, rows, seed=1, concurrency=2)
    assert set(results) == {"a", "b"}
    assert len(client.calls) == 6
    assert all(attempts == 1 for _, attempts in client.calls)
    intake = [q for q, _ in client.calls if "commitment" in q]
    assert len(intake) == 2


def test_shuffled_questions_keep_every_option(cal):
    import random

    q = cal.shuffled_questions(random.Random(3))
    assert set(q["commitment"].criteria) == set(cal.CHOICES)


def test_baseline_fact_rule_follows_the_frozen_163_bars(baseline):
    persist = baseline.decide_fact_163(_r163("fact", bio=0.9, family="preference"))
    assert persist == "persist"
    assert baseline.decide_fact_163(_r163("reminder", bio=0.9)) == "hold"
    low = SystemOneResult(
        outcome="ok",
        answers={
            "speech_act": _choice("fact", 0.6),
            "family": _choice("preference"),
            "biography": _noul(0.9),
        },
    )
    assert baseline.decide_fact_163(low) == "hold"
    assert (
        baseline.decide_fact_163(SystemOneResult(outcome="skip", skip_reason="error"))
        == "fallback"
    )
