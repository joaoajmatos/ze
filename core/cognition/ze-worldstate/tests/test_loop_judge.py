from __future__ import annotations

import math

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from ze_worldstate import loop_judge as lj
from ze_worldstate.loop_judge import (
    LOOP_QUESTIONS,
    LoopGateSurfaceConfig,
    build_state,
    decide,
    loop_gate_surface_config,
)


def _settings(block):
    return {"system_one": {"surfaces": {"loop_gate": block}}}


def test_missing_or_invalid_block_is_disabled():
    assert loop_gate_surface_config({}) == LoopGateSurfaceConfig()
    assert loop_gate_surface_config(None) == LoopGateSurfaceConfig()
    assert loop_gate_surface_config(_settings("nope")) == LoopGateSurfaceConfig()
    assert not LoopGateSurfaceConfig().enabled


def test_enabled_with_null_bar_is_uncalibrated():
    cfg = loop_gate_surface_config(
        _settings(
            {
                "enabled": True,
                "loop_hold": 0.5,
                "explicit_hold": None,
                "resolves_hold": 0.5,
            }
        )
    )
    assert cfg.enabled and not cfg.calibrated


def test_all_bars_set_is_calibrated():
    cfg = loop_gate_surface_config(
        _settings(
            {
                "enabled": True,
                "loop_hold": 0.5,
                "explicit_hold": 0.6,
                "resolves_hold": 0.7,
            }
        )
    )
    assert cfg.calibrated
    assert (cfg.loop_hold, cfg.explicit_hold, cfg.resolves_hold) == (0.5, 0.6, 0.7)


@pytest.mark.parametrize("bad", ["0.5", math.nan, 1.5, -0.1, True])
def test_bad_bars_become_none(bad):
    cfg = loop_gate_surface_config(
        _settings(
            {
                "enabled": True,
                "loop_hold": bad,
                "explicit_hold": 0.5,
                "resolves_hold": 0.5,
            }
        )
    )
    assert cfg.loop_hold is None
    assert not cfg.calibrated


def test_two_noul_questions_without_criteria():
    assert set(LOOP_QUESTIONS) == {"is_open_concern", "resolves_existing"}
    for q in LOOP_QUESTIONS.values():
        assert q.type == "noul"
        assert q.criteria is None


def test_explicit_declaration_belongs_to_the_commitment_intake_only():
    assert not hasattr(lj, "Q_EXPLICIT")
    assert not hasattr(lj, "questions_for")
    assert "explicit_declaration" not in LOOP_QUESTIONS


@pytest.mark.parametrize(
    "prov,key,cap",
    [
        ("conversation", "user", 1000),
        ("email", "email", 1500),
        ("calendar", "event", 600),
        ("ingestion", "facts", 1500),
    ],
)
def test_build_state_caps_and_keys(prov, key, cap):
    state = build_state("x" * 20000, prov)
    assert state == {"source": prov, key: "x" * cap}


def test_build_state_has_no_extra_keys_for_short_text():
    assert build_state("hello", "conversation") == {
        "source": "conversation",
        "user": "hello",
    }


def test_capped_text_matches_state_cap():
    assert len(lj.capped_text("y" * 5000, "calendar")) == 600


def _result(**noul):
    answers = {k: SystemOneAnswer(type="noul", noul=v) for k, v in noul.items()}
    return SystemOneResult(outcome="ok", answers=answers)


CFG = LoopGateSurfaceConfig(
    enabled=True, loop_hold=0.5, explicit_hold=0.6, resolves_hold=0.7
)


def test_decide_skip_is_fallback():
    d = decide(SystemOneResult(outcome="skip", skip_reason="timeout"), CFG, "email")
    assert (d.kind, d.reason) == ("fallback", "timeout")


def test_decide_missing_answer_is_invalid():
    d = decide(_result(is_open_concern=0.9), CFG, "email")
    assert (d.kind, d.reason) == ("fallback", "invalid_answer")


def test_decide_non_noul_answer_is_invalid():
    res = SystemOneResult(
        outcome="ok",
        answers={
            "is_open_concern": SystemOneAnswer(
                type="choice", choice="a", confidence=0.9
            ),
            "resolves_existing": SystemOneAnswer(type="noul", noul=0.1),
        },
    )
    assert decide(res, CFG, "email").reason == "invalid_answer"


def test_decide_null_bar_is_uncalibrated():
    cfg = LoopGateSurfaceConfig(
        enabled=True, loop_hold=0.5, explicit_hold=None, resolves_hold=0.7
    )
    d = decide(_result(is_open_concern=0.9, resolves_existing=0.1), cfg, "email")
    assert (d.kind, d.reason) == ("fallback", "uncalibrated")


def test_resolves_wins_and_concern_not_consumed():
    d = decide(
        _result(is_open_concern=0.9, resolves_existing=0.7),
        CFG,
        "email",
    )
    assert d.kind == "resolve"
    assert d.consumed == frozenset({"resolves_existing"})


def test_below_loop_hold_is_hold():
    d = decide(_result(is_open_concern=0.49, resolves_existing=0.1), CFG, "email")
    assert (d.kind, d.reason) == ("hold", "not_open_concern")
    assert d.consumed == frozenset({"is_open_concern", "resolves_existing"})


def test_at_the_bar_is_positive():
    d = decide(_result(is_open_concern=0.5, resolves_existing=0.1), CFG, "email")
    assert d.kind == "create_suspected"
    assert d.consumed == frozenset({"is_open_concern", "resolves_existing"})
    assert (
        decide(_result(is_open_concern=0.1, resolves_existing=0.7), CFG, "email").kind
        == "resolve"
    )


def test_decide_out_of_range_noul_is_invalid():
    d = decide(
        _result(is_open_concern=1.5, resolves_existing=0.1),
        CFG,
        "email",
    )
    assert (d.kind, d.reason) == ("fallback", "invalid_answer")
