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


# ── decide(): exact R7 rules 3, 4 and 6-9 (US3) ───────────────────────────────

from ze_agents.system_one import SystemOneResult  # noqa: E402

_ALL = frozenset({"speech_act", "family", "biography"})


def test_rule_3_client_skip_is_skip_with_client_reason():
    decision = decide(SystemOneResult(outcome="skip", skip_reason="timeout"), _CAL)
    assert (decision.kind, decision.reason) == ("skip", "timeout")
    assert decision.consumed == frozenset()


def test_rule_6_unsure_fact_act_holds():
    decision = decide(make_result("fact", "preference", act_confidence=0.4), _CAL)
    assert (decision.kind, decision.reason) == ("hold", "act_unsure")
    assert decision.consumed == frozenset({"speech_act"})


def test_rule_5_runs_before_rule_6_unsure_reminder_is_not_fact():
    decision = decide(make_result("reminder", "drop", act_confidence=0.3), _CAL)
    assert (decision.kind, decision.reason) == ("hold", "not_fact")


@pytest.mark.parametrize("label", ["drop", "ephemeral", "banana"])
def test_rule_7_drop_or_unknown_family_holds(label):
    decision = decide(make_result("fact", label), _CAL)
    assert (decision.kind, decision.reason) == ("hold", "family_drop")
    assert decision.consumed == frozenset({"speech_act", "family"})


def test_rule_8_unsure_family_holds():
    decision = decide(make_result("fact", "preference", family_confidence=0.4), _CAL)
    assert (decision.kind, decision.reason) == ("hold", "family_unsure")
    assert decision.consumed == frozenset({"speech_act", "family"})


def test_rule_9_even_biography_holds_despite_confident_fact():
    decision = decide(make_result("fact", "preference", noul=0.5), _CAL)
    assert (decision.kind, decision.reason) == ("hold", "not_biography")
    assert decision.consumed == _ALL


def test_rule_9_boundary_at_bar_persists():
    decision = decide(make_result("fact", "preference", noul=0.7), _CAL)
    assert decision.kind == "persist"


def test_bars_are_independent():
    cfg = SpeechActSurfaceConfig(enabled=True, choice_hold=0.9, biography_hold=0.2)
    assert (
        decide(make_result("fact", "preference", act_confidence=0.8), cfg).reason
        == "act_unsure"
    )
    assert decide(make_result("fact", "preference", noul=0.3), cfg).kind == "persist"
    cfg = SpeechActSurfaceConfig(enabled=True, choice_hold=0.2, biography_hold=0.9)
    assert (
        decide(make_result("fact", "preference", act_confidence=0.3), cfg).kind
        == "persist"
    )
    assert (
        decide(make_result("fact", "preference", noul=0.8), cfg).reason
        == "not_biography"
    )


def _invalid(mutate):
    result = make_result("fact", "preference")
    mutate(result.answers)
    return decide(result, _CAL)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.pop("speech_act"),
        lambda a: a.pop("family"),
        lambda a: a.pop("biography"),
        lambda a: setattr(a["speech_act"], "confidence", None),
        lambda a: setattr(a["family"], "choice", None),
        lambda a: setattr(a["biography"], "noul", None),
        lambda a: a.update(
            biography=SystemOneAnswer(type="choice", choice="x", confidence=0.9)
        ),
    ],
)
def test_rule_4_malformed_answer_is_skip_invalid_answer(mutate):
    decision = _invalid(mutate)
    assert (decision.kind, decision.reason) == ("skip", "invalid_answer")
    assert decision.consumed == frozenset()
