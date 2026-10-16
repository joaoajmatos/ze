from __future__ import annotations

import math

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from ze_worldstate import corroboration_judge as cj
from ze_worldstate.corroboration_judge import (
    Q_SAME,
    CorroborationSurfaceConfig,
    build_state,
    corroboration_surface_config,
    decide,
)


def _settings(block):
    return {"system_one": {"surfaces": {"corroboration": block}}}


def _result(score):
    return SystemOneResult(
        outcome="ok", answers={Q_SAME: SystemOneAnswer(type="noul", noul=score)}
    )


CFG = CorroborationSurfaceConfig(enabled=True, corroborate_hold=0.6, promote_hold=0.85)


def test_question_is_one_noul_without_criteria():
    assert Q_SAME == "same_concern"
    assert cj.QUESTION.type == "noul"
    assert cj.QUESTION.criteria is None


def test_missing_or_invalid_block_is_disabled():
    assert corroboration_surface_config({}) == CorroborationSurfaceConfig()
    assert corroboration_surface_config(None) == CorroborationSurfaceConfig()
    assert corroboration_surface_config(_settings("nope")) == CorroborationSurfaceConfig()
    assert not CorroborationSurfaceConfig().enabled


def test_null_bar_is_uncalibrated():
    cfg = corroboration_surface_config(
        _settings({"enabled": True, "corroborate_hold": None, "promote_hold": 0.9})
    )
    assert cfg.enabled and not cfg.calibrated


def test_both_bars_set_is_calibrated():
    cfg = corroboration_surface_config(
        _settings({"enabled": True, "corroborate_hold": 0.6, "promote_hold": 0.85})
    )
    assert cfg.calibrated
    assert (cfg.corroborate_hold, cfg.promote_hold) == (0.6, 0.85)


def test_equal_bars_are_calibrated():
    assert CorroborationSurfaceConfig(True, 0.7, 0.7).calibrated


def test_corroborate_above_promote_is_uncalibrated():
    cfg = corroboration_surface_config(
        _settings({"enabled": True, "corroborate_hold": 0.9, "promote_hold": 0.6})
    )
    assert not cfg.calibrated


@pytest.mark.parametrize("bad", ["0.5", math.nan, 1.5, -0.1, True])
def test_bad_bars_become_none(bad):
    cfg = corroboration_surface_config(
        _settings({"enabled": True, "corroborate_hold": bad, "promote_hold": 0.9})
    )
    assert cfg.corroborate_hold is None
    assert not cfg.calibrated


def test_state_shape_and_caps():
    state = build_state("t" * 500, "x" * 5000, "email")
    assert state == {"loop": "t" * 200, "source": "email", "email": "x" * 1500}


@pytest.mark.parametrize(
    "inflow,key,cap",
    [
        ("conversation", "user", 1000),
        ("email", "email", 1500),
        ("calendar", "event", 600),
        ("ingestion", "facts", 1500),
    ],
)
def test_state_uses_the_168_key_per_inflow(inflow, key, cap):
    state = build_state("Renew passport", "y" * 9000, inflow)
    assert state[key] == "y" * cap
    assert state["source"] == inflow


def test_disabled_is_fallback():
    d = decide(_result(0.99), CorroborationSurfaceConfig())
    assert (d.kind, d.reason) == ("fallback", "disabled")


def test_uncalibrated_is_fallback():
    d = decide(_result(0.99), CorroborationSurfaceConfig(enabled=True))
    assert (d.kind, d.reason) == ("fallback", "uncalibrated")


def test_skip_is_fallback_with_reason():
    d = decide(SystemOneResult(outcome="skip", skip_reason="timeout"), CFG)
    assert (d.kind, d.reason) == ("fallback", "timeout")


def test_skip_without_reason_is_error():
    assert decide(SystemOneResult(outcome="skip"), CFG).reason == "error"


@pytest.mark.parametrize("bad", [None, math.nan, 1.2, -0.2, True])
def test_invalid_noul_is_fallback(bad):
    res = SystemOneResult(
        outcome="ok", answers={Q_SAME: SystemOneAnswer(type="noul", noul=bad)}
    )
    d = decide(res, CFG)
    assert (d.kind, d.reason) == ("fallback", "invalid_answer")


def test_missing_and_non_noul_answers_are_invalid():
    assert decide(SystemOneResult(outcome="ok"), CFG).reason == "invalid_answer"
    res = SystemOneResult(
        outcome="ok", answers={Q_SAME: SystemOneAnswer(type="score", score=0.9)}
    )
    assert decide(res, CFG).reason == "invalid_answer"


@pytest.mark.parametrize(
    "score,kind,reason",
    [
        (0.95, "promote", "same_concern"),
        (0.85, "promote", "same_concern"),
        (0.849, "corroborate", "same_concern"),
        (0.6, "corroborate", "same_concern"),
        (0.599, "not_same", "below_bar"),
        (0.0, "not_same", "below_bar"),
    ],
)
def test_decision_table(score, kind, reason):
    d = decide(_result(score), CFG)
    assert (d.kind, d.reason, d.score) == (kind, reason, score)


def test_equal_bars_promote_at_the_bar():
    cfg = CorroborationSurfaceConfig(True, 0.7, 0.7)
    assert decide(_result(0.7), cfg).kind == "promote"
