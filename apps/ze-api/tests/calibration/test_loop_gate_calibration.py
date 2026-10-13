"""Dataset shape and pure scoring of eval/calibration/loop_gate.py (phase 168). No network."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

_SCRIPT = Path(__file__).resolve().parents[4] / "eval/calibration/loop_gate.py"


@pytest.fixture(scope="module")
def calib():
    spec = importlib.util.spec_from_file_location("loop_gate_calibration", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def test_sets_pass_shape_checks(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    assert calib.shape_problems(tuned, holdout) == []


def test_set_sizes_and_coverage(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    for lang in calib.LANGS:
        assert sum(r.lang == lang for r in tuned) >= 40
        assert sum(r.lang == lang for r in holdout) >= 20
    for rows in (tuned, holdout):
        for prov in calib.PROVENANCES:
            sub = [r for r in rows if r.provenance == prov]
            assert any(r.gold_loop for r in sub) and any(not r.gold_loop for r in sub)


def test_no_holdout_text_in_tuned(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    held = {calib._norm(r.text) for r in holdout}
    assert not [r.id for r in tuned if calib._norm(r.text) in held]


def test_shape_problems_catch_violations(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    bad = [
        calib.Row(
            **{
                **tuned[0].__dict__,
                "id": "x",
                "gold_loop": False,
                "gold_explicit": True,
            }
        )
    ]
    assert any("gold_explicit" in p for p in calib.shape_problems(bad, holdout))
    leaked = [calib.Row(**{**tuned[0].__dict__, "text": holdout[0].text})]
    assert any(
        "held-out" in p for p in calib.shape_problems(leaked + tuned[1:], holdout)
    )


def _row(calib, i, prov, loop, explicit=False, resolves=False, lang="en"):
    return calib.Row(f"r{i}", lang, prov, "t", loop, explicit, resolves, "k")


def test_score_and_verdict(calib):
    rows = [
        _row(calib, 1, "conversation", True, explicit=True),
        _row(calib, 2, "email", True),
        _row(calib, 3, "email", False),
        _row(calib, 4, "email", False, resolves=True),
    ]
    good = {
        "r1": "create_declared",
        "r2": "create_suspected",
        "r3": "hold",
        "r4": "resolve",
    }
    c = calib.score(rows, good)
    assert (c.precision, c.recall, c.false_creates, c.false_resolve) == (1.0, 1.0, 0, 0)
    assert c.explicit_acc == 1.0 and c.resolves_acc == 1.0
    ok, failing = calib.verdict(c, c)
    assert ok and failing == []

    bad = {**good, "r3": "create_suspected"}
    cb = calib.score(rows, bad)
    assert cb.false_creates == 1
    ok, failing = calib.verdict(cb, c)
    assert not ok and any("false creates" in f for f in failing)


def test_fallback_counts_as_miss_not_false_create(calib):
    rows = [_row(calib, 1, "email", True), _row(calib, 2, "email", False)]
    c = calib.score(rows, {"r1": "fallback", "r2": "fallback"})
    assert c.recall == 0.0 and c.false_creates == 0 and c.fallback == 2


def test_verdict_recall_and_precision_clauses(calib):
    haiku = calib.Counts(positives=10, hit_positives=9, creates=10, correct_creates=9)
    lower_recall = calib.Counts(
        positives=10, hit_positives=8, creates=8, correct_creates=8
    )
    ok, failing = calib.verdict(lower_recall, haiku)
    assert not ok and any("recall" in f for f in failing)
    imprecise = calib.Counts(
        positives=10, hit_positives=9, creates=10, correct_creates=8
    )
    ok, failing = calib.verdict(imprecise, haiku)
    assert not ok and any("precision" in f for f in failing)
    within_slack = calib.Counts(
        positives=10, hit_positives=9, creates=9, correct_creates=9
    )
    assert calib.verdict(within_slack, haiku)[0]


def test_haiku_kind_mirrors_109(calib):
    g = calib._ExtractionGateResult
    assert calib.haiku_kind(None) == "fallback"
    assert calib.haiku_kind(g(False, "Done", False, True)) == "resolve"
    assert calib.haiku_kind(g(True, "Do it", True, False)) == "create_declared"
    assert calib.haiku_kind(g(True, "Do it", False, False)) == "create_suspected"
    assert calib.haiku_kind(g(True, "", False, False)) == "hold"


def test_suggest_bars_picks_zero_false_create_plateau(calib):
    rows = [_row(calib, 1, "email", True), _row(calib, 2, "email", False)]

    def res(c, r):
        return SystemOneResult(
            outcome="ok",
            answers={
                "is_open_concern": SystemOneAnswer(type="noul", noul=c),
                "resolves_existing": SystemOneAnswer(type="noul", noul=r),
            },
        )

    results = {"r1": res(0.95, 0.0), "r2": res(0.2, 0.0)}
    cfg = calib.suggest_bars(rows, results)
    assert cfg is not None and 0.5 <= cfg.loop_hold <= 0.95
    c = calib.score(rows, calib._kinds_for(rows, results, cfg))
    assert c.false_creates == 0 and c.recall == 1.0
    bad = {**results, "r2": res(0.99, 0.0)}
    assert calib.suggest_bars(rows, bad) is None
