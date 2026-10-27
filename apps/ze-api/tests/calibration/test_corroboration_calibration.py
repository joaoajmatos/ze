"""Dataset shape and pure scoring of eval/calibration/corroboration.py (phase 172). No network.

The live calibration path builds its client and embedder lazily inside `main_async`, so importing
the script under pytest constructs nothing and never reaches OpenRouter or System One.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

_SCRIPT = Path(__file__).resolve().parents[4] / "eval/calibration/corroboration.py"


@pytest.fixture(scope="module")
def calib():
    spec = importlib.util.spec_from_file_location("corroboration_calibration", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def _result(noul: float) -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        answers={"same_concern": SystemOneAnswer(type="noul", noul=noul)},
    )


def _row(
    calib,
    i: int,
    gold_same: bool,
    *,
    kind: str | None = None,
    inflow: str = "email",
):
    return calib.Row(
        f"r{i}",
        "en",
        "loop title",
        "conversation",
        inflow,
        "text",
        "new title",
        gold_same,
        kind or ("same" if gold_same else "unrelated"),
    )


def _counts(
    calib,
    *,
    positives: int,
    counted: int,
    true_counted: int,
    false_counted: int = 0,
    promoted: int = 0,
    false_promotions: int = 0,
    fallback: int = 0,
):
    return calib.Counts(
        n=positives,
        fallback=fallback,
        positives=positives,
        counted=counted,
        true_counted=true_counted,
        false_counted=false_counted,
        promoted=promoted,
        false_promotions=false_promotions,
    )


# --- dataset shape (FR-018) -----------------------------------------------------------


def test_sets_pass_shape_checks(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    assert calib.shape_problems(tuned, holdout) == []


def test_set_sizes_and_hard_negative_coverage(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    for lang in calib.LANGS:
        scoped = [r for r in tuned if r.lang == lang]
        assert len(scoped) >= calib.MIN_TUNED_PER_LANG
        hard = [r for r in scoped if r.kind in calib.HARD_NEGATIVE_KINDS]
        assert len(hard) * 3 >= len(scoped)
        for inflow in calib.INFLOWS:
            assert sum(r.inflow == inflow for r in scoped) >= calib.MIN_TUNED_PER_INFLOW
    for lang in calib.LANGS:
        scoped = [r for r in holdout if r.lang == lang]
        assert len(scoped) >= calib.MIN_HOLDOUT_PER_LANG
        hard = [r for r in scoped if r.kind in calib.HARD_NEGATIVE_KINDS]
        assert len(hard) * 3 >= len(scoped)
        for inflow in calib.INFLOWS:
            assert sum(r.inflow == inflow for r in scoped) >= calib.MIN_HOLDOUT_PER_INFLOW


def test_no_holdout_text_in_tuned(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    held = {calib.harness.norm(r.text) for r in holdout}
    assert not [r.id for r in tuned if calib.harness.norm(r.text) in held]


def test_shape_problems_catch_violations(calib):
    tuned, holdout = calib.load_rows(calib.TUNED), calib.load_rows(calib.HOLDOUT)
    bad = [
        calib.Row(
            **{**tuned[0].__dict__, "id": "x", "kind": "unrelated", "gold_same": True}
        )
    ]
    assert any("gold_same" in p for p in calib.shape_problems(bad, holdout))
    leaked = [calib.Row(**{**tuned[0].__dict__, "text": holdout[0].text})]
    assert any("held-out" in p for p in calib.shape_problems(leaked + tuned[1:], holdout))


def _module_scope_import_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    return roots


def _function_imports(tree: ast.Module, func_name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == func_name
        ):
            return {
                child.module or ""
                for child in ast.walk(node)
                if isinstance(child, ast.ImportFrom)
            }
    return set()


def test_question_and_live_path_are_offline(calib):
    assert calib.Q_SAME == "same_concern"
    assert calib.QUESTION.type == "noul"
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    # No ze_core import at module scope: a future one could touch the client or the embedder at
    # collection time, and the live path must stay function-local.
    assert "ze_core" not in _module_scope_import_roots(tree)
    assert not hasattr(calib, "OpenRouterSystemOneClient")
    # The guard is not vacuous: the live client really is imported inside the harness's make_client.
    harness_tree = ast.parse(Path(calib.harness.__file__).read_text(encoding="utf-8"))
    assert "ze_core" not in _module_scope_import_roots(harness_tree)
    assert "ze_core.openrouter.system_one" in _function_imports(harness_tree, "make_client")


# --- pure scoring and the decision helpers ---------------------------------------------


def test_score_counts_fallback_as_miss_not_false_promotion(calib):
    rows = [_row(calib, 1, True), _row(calib, 2, False)]
    c = calib.score(rows, {"r1": "fallback", "r2": "fallback"})
    assert c.fallback == 2
    assert c.counted == 0 and c.promoted == 0
    assert c.false_counted == 0 and c.false_promotions == 0
    assert c.recall == 0.0


def test_score_flags_promote_on_a_negative_as_false_promotion(calib):
    rows = [_row(calib, 1, True), _row(calib, 2, False)]
    c = calib.score(rows, {"r1": "corroborate", "r2": "promote"})
    assert c.promoted == 1 and c.false_promotions == 1
    assert c.false_counted == 1


def test_verdict_fails_on_any_false_promotion(calib):
    perfect = _counts(calib, positives=10, counted=10, true_counted=10)
    system = _counts(
        calib, positives=10, counted=10, true_counted=10, promoted=1, false_promotions=1
    )
    ok, failing = calib.verdict(system, perfect)
    assert not ok and failing == ["false promotions 1 != 0"]


def test_verdict_fails_below_precision_floor(calib):
    e5 = _counts(calib, positives=100, counted=100, true_counted=85, false_counted=15)
    system = _counts(
        calib, positives=100, counted=100, true_counted=89, false_counted=11
    )
    ok, failing = calib.verdict(system, e5)
    assert not ok and len(failing) == 1 and "0.9" in failing[0]


def test_verdict_fails_below_e5_precision(calib):
    e5 = _counts(calib, positives=100, counted=100, true_counted=95, false_counted=5)
    system = _counts(
        calib, positives=100, counted=100, true_counted=92, false_counted=8
    )
    ok, failing = calib.verdict(system, e5)
    assert not ok and len(failing) == 1 and "E5" in failing[0]


def test_verdict_fails_below_e5_recall_minus_slack(calib):
    e5 = _counts(calib, positives=100, counted=100, true_counted=90, false_counted=10)
    system = _counts(
        calib, positives=100, counted=30, true_counted=29, false_counted=1
    )
    ok, failing = calib.verdict(system, e5)
    assert not ok and len(failing) == 1 and "recall" in failing[0]


def test_suggest_bars_none_without_a_zero_false_promotion_promote_hold(calib):
    rows = [_row(calib, 1, True), _row(calib, 2, False)]
    results = {r.id: _result(0.9 if r.gold_same else 0.99) for r in rows}
    assert calib.suggest_bars(rows, results) is None


def test_suggest_bars_keeps_corroborate_hold_at_or_below_promote_hold(calib):
    rows = [_row(calib, 1, True), _row(calib, 2, False)]
    results = {r.id: _result(0.9 if r.gold_same else 0.2) for r in rows}
    cfg = calib.suggest_bars(rows, results)
    assert cfg is not None
    assert cfg.corroborate_hold <= cfg.promote_hold
    counts = calib.score(rows, calib.kinds_for(rows, results, cfg))
    assert counts.false_promotions == 0 and counts.precision >= calib.PRECISION_FLOOR


def _parse_bars(calib, text):
    return calib.harness.bars_config(
        calib.CorroborationSurfaceConfig, text, ("corroborate_hold", "promote_hold")
    )


@pytest.mark.parametrize("bars", ["0.6,1.5", "-0.5,0.5", "nan,0.5", "0.9,0.6", "0.6"])
def test_parse_bars_rejects_invalid_bars(calib, bars):
    with pytest.raises(SystemExit):
        _parse_bars(calib, bars)


def test_parse_bars_accepts_a_valid_pair(calib):
    cfg = _parse_bars(calib, "0.6,0.85")
    assert (cfg.corroborate_hold, cfg.promote_hold) == (0.6, 0.85)
