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


def test_choice_accuracy_ignores_rows_where_the_turn_created_something(cal):
    plain = _row(cal, id="p", gold_choice="none")
    booked = _row(cal, id="b", gold_choice="loop", turn_created="reminder")
    results = {
        "p": cal.RowResults(_system("none"), _r163("drop"), _r168()),
        "b": cal.RowResults(_system("reminder"), _r163("reminder"), _r168()),
    }
    rows = [plain, booked]
    c = cal.score(
        rows,
        cal.preds_for(rows, results, _bars(cal)),
        cal.choices_for(rows, results),
    )
    assert (c.choice_ok, c.choice_total) == (1, 1)
    assert (c.link_ok, c.link_total) == (1, 1)


def test_link_accuracy_misses_when_the_turn_resolved_a_loop_instead(cal):
    booked = _row(cal, id="g", gold_choice="goal", turn_created="goal")
    linked = {"g": cal.RowResults(_system("goal"), _r163("goal"), _r168())}
    c = cal.score([booked], cal.preds_for([booked], linked, _bars(cal)))
    assert c.link_acc == 1.0
    resolved = {
        "g": cal.RowResults(_system("goal", resolves=0.99), _r163("goal"), _r168())
    }
    c = cal.score([booked], cal.preds_for([booked], resolved, _bars(cal)))
    assert (c.link_ok, c.link_total) == (0, 1)


def test_also_loop_row_accepts_a_loop_create_without_penalty(cal):
    mixed = _row(
        cal, id="m", gold_choice="fact", gold_family="constraint", kind="mixed"
    )
    mixed.also_loop = True
    plain = _row(cal, id="m2", gold_choice="fact", gold_family="constraint")
    loop_answer = {
        "m": cal.RowResults(_system("loop", concern=0.95), _r163("fact"), _r168()),
        "m2": cal.RowResults(_system("loop", concern=0.95), _r163("fact"), _r168()),
    }
    c = cal.score(
        [mixed],
        cal.preds_for([mixed], loop_answer, _bars(cal)),
        cal.choices_for([mixed], loop_answer),
    )
    assert c.false_creates == 0
    assert (c.loop_pred, c.fact_pos) == (0, 0)
    assert (c.choice_ok, c.choice_total) == (1, 1)
    strict = cal.score([plain], cal.preds_for([plain], loop_answer, _bars(cal)))
    assert strict.false_creates == 1 and strict.fact_pos == 1


def test_also_loop_row_still_scores_a_fact_answer_as_a_hit(cal):
    mixed = _row(
        cal, id="m", gold_choice="fact", gold_family="constraint", kind="mixed"
    )
    mixed.also_loop = True
    fact_answer = {
        "m": cal.RowResults(
            _system("fact", bio=0.9, family="constraint"), _r163("fact"), _r168()
        )
    }
    c = cal.score([mixed], cal.preds_for([mixed], fact_answer, _bars(cal)))
    assert (c.fact_hits, c.fact_pos) == (1, 1)


def _good(cal, **over):
    base = dict(
        fact_pos=10,
        fact_pred=10,
        fact_hits=10,
        loop_pos=10,
        loop_pred=10,
        loop_hits=10,
        choice_total=10,
        choice_ok=10,
    )
    base.update(over)
    return cal.Counts(**base)


def test_verdict_fails_when_the_intake_resolves_more_than_the_baseline(cal):
    ok, failing = cal.verdict(_good(cal, false_resolve=1), _good(cal, false_resolve=0))
    assert not ok
    assert failing == ["false resolves 1 > baseline 0"]


def test_verdict_allows_false_resolves_up_to_the_baseline(cal):
    assert cal.verdict(_good(cal, false_resolve=1), _good(cal, false_resolve=1))[0]
    assert cal.verdict(_good(cal, false_resolve=0), _good(cal, false_resolve=2))[0]


def test_false_resolve_counts_a_resolve_on_a_row_that_is_not_a_resolves_row(cal):
    ingest = _row(cal, id="i", gold_choice="ingest")
    results = {
        "i": cal.RowResults(
            _system("ingest", resolves=0.95), _r163("ingest"), _r168(resolves=0.95)
        )
    }
    system = cal.score([ingest], cal.preds_for([ingest], results, _bars(cal)))
    base = cal.score([ingest], cal.baseline_preds([ingest], results))
    assert system.false_resolve == 1 and base.false_resolve == 1


def test_choice_accuracy_excludes_gold_resolves_rows(cal):
    plain = _row(cal, id="p", gold_choice="none")
    resolves = _row(cal, id="r", gold_choice="none", gold_resolves=True)
    results = {
        "p": cal.RowResults(_system("none"), _r163("drop"), _r168()),
        "r": cal.RowResults(
            _system("fact", resolves=0.95), _r163("fact"), _r168(resolves=0.95)
        ),
    }
    rows = [plain, resolves]
    c = cal.score(
        rows,
        cal.preds_for(rows, results, _bars(cal)),
        cal.choices_for(rows, results),
    )
    assert (c.choice_ok, c.choice_total) == (1, 1)
    assert c.resolves_ok == 2


def test_verdict_fails_on_any_waiting_on_write(cal):
    ok, failing = cal.verdict(
        _good(cal, waiting_total=5, waiting_written=1), _good(cal)
    )
    assert not ok
    assert failing == ["waiting_on rows written to a store 1 != 0"]
    assert cal.verdict(_good(cal, waiting_total=5, waiting_written=0), _good(cal))[0]


@pytest.mark.parametrize(
    "answers",
    [
        dict(commitment="loop", concern=0.95),
        dict(commitment="none", resolves=0.95),
        dict(commitment="fact", bio=0.95, family="identity"),
    ],
)
def test_a_waiting_on_row_that_writes_is_counted(cal, answers):
    row = _row(cal, id="w", gold_choice="waiting_on", kind="waiting_on")
    results = {"w": cal.RowResults(_system(**answers), _r163("drop"), _r168())}
    c = cal.score([row], cal.preds_for([row], results, _bars(cal)))
    assert (c.waiting_total, c.waiting_written) == (1, 1)


def test_a_held_waiting_on_row_writes_nothing(cal):
    row = _row(cal, id="w", gold_choice="waiting_on", kind="waiting_on")
    results = {"w": cal.RowResults(_system("waiting_on"), _r163("drop"), _r168())}
    c = cal.score([row], cal.preds_for([row], results, _bars(cal)))
    assert (c.waiting_total, c.waiting_written) == (1, 0)
