"""Speech-act System One judge — config, questions, state, decision table."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from ze_agents.system_one import SystemOneAnswer

from ze_memory.extractor import KEEP_FAMILIES, PredicateFamily
from ze_memory.speech_act_judge import (
    SPEECH_ACT_QUESTIONS,
    SpeechActSurfaceConfig,
    build_state,
    speech_act_surface_config,
)
from ze_memory.types import SpeechAct


def _cfg(**speech_act) -> dict:
    return {"system_one": {"surfaces": {"speech_act": speech_act}}}


def test_missing_block_is_disabled():
    cfg = speech_act_surface_config({})
    assert cfg == SpeechActSurfaceConfig(
        enabled=False, choice_hold=None, biography_hold=None
    )
    assert not cfg.calibrated


def test_enabled_with_null_bar_is_uncalibrated():
    assert not speech_act_surface_config(
        _cfg(enabled=True, choice_hold=0.7, biography_hold=None)
    ).calibrated
    assert not speech_act_surface_config(
        _cfg(enabled=True, choice_hold=None, biography_hold=0.7)
    ).calibrated


def test_enabled_with_both_bars_is_calibrated():
    cfg = speech_act_surface_config(
        _cfg(enabled=True, choice_hold=0.6, biography_hold=0.8)
    )
    assert cfg.calibrated
    assert (cfg.choice_hold, cfg.biography_hold) == (0.6, 0.8)


def test_disabled_with_bars_is_not_calibrated():
    assert not speech_act_surface_config(
        _cfg(enabled=False, choice_hold=0.6, biography_hold=0.8)
    ).calibrated


@pytest.mark.parametrize("bad", [1.5, -0.1, "high", True, float("nan")])
def test_bad_bar_becomes_none(bad):
    cfg = speech_act_surface_config(
        _cfg(enabled=True, choice_hold=bad, biography_hold=0.8)
    )
    assert cfg.choice_hold is None
    assert not cfg.calibrated


def test_accepts_object_with_config_dict():
    settings = SimpleNamespace(
        config=_cfg(enabled=True, choice_hold=0.5, biography_hold=0.5)
    )
    assert speech_act_surface_config(settings).calibrated


def test_none_settings_is_disabled():
    assert not speech_act_surface_config(None).enabled


def test_question_keys():
    assert set(SPEECH_ACT_QUESTIONS) == {"speech_act", "family", "biography"}


def test_speech_act_options_follow_enum_order():
    q = SPEECH_ACT_QUESTIONS["speech_act"]
    assert q.type == "choice"
    assert list(q.criteria) == [a.value for a in SpeechAct]


def test_family_options_are_keep_families_plus_drop():
    q = SPEECH_ACT_QUESTIONS["family"]
    assert q.type == "choice"
    assert list(q.criteria) == [f.value for f in PredicateFamily] + ["drop"]
    assert set(q.criteria) == KEEP_FAMILIES | {"drop"}


def test_biography_is_noul():
    assert SPEECH_ACT_QUESTIONS["biography"].type == "noul"


def test_every_speech_act_criterion_has_english_and_portuguese_example():
    for label, text in SPEECH_ACT_QUESTIONS["speech_act"].criteria.items():
        assert text.strip(), label
    joined = " ".join(SPEECH_ACT_QUESTIONS["speech_act"].criteria.values())
    for pt in ("lembra-me", "esquece", "prefiro"):
        assert pt in joined


def test_build_state_caps_assistant_and_has_only_two_keys():
    state = build_state("hi there", "x" * 1500)
    assert set(state) == {"user", "assistant"}
    assert state["user"] == "hi there"
    assert len(state["assistant"]) == 1000


# ── decide(): rules 5 and 10 (US1) ────────────────────────────────────────────

from ze_memory.speech_act_judge import decide  # noqa: E402
from tests.fixtures.speech_act_gold import (  # noqa: E402
    NON_FACT,
    PERSIST,
    make_result,
)

_CAL = SpeechActSurfaceConfig(enabled=True, choice_hold=0.6, biography_hold=0.7)


@pytest.mark.parametrize("turn", NON_FACT, ids=lambda t: t.id)
def test_non_fact_acts_hold_not_fact(turn):
    decision = decide(turn.result(), _CAL)
    assert (decision.kind, decision.reason) == ("hold", "not_fact")
    assert decision.consumed == frozenset({"speech_act"})
    assert decision.family is None


@pytest.mark.parametrize("turn", PERSIST, ids=lambda t: t.id)
def test_confident_fact_persists_with_chosen_family(turn):
    decision = decide(turn.result(), _CAL)
    assert decision.kind == "persist"
    assert decision.family == turn.family
    assert decision.consumed == frozenset({"speech_act", "family", "biography"})


def test_unknown_act_label_goes_through_admit_to_drop_and_holds():
    result = make_result("fact", "preference")
    result.answers["speech_act"] = SystemOneAnswer(
        type="choice", choice="remind", confidence=0.99
    )
    decision = decide(result, _CAL)
    assert (decision.kind, decision.reason) == ("hold", "not_fact")
