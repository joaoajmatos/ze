"""Phase 163 — System One admission gate (mocked client, no vendor calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_memory.speech_act_gate import (
    AdmissionThresholds,
    thresholds_from_settings,
)
from ze_memory.extractor import gather_fact_proposals

THRESHOLDS = AdmissionThresholds(
    act_min_peakedness=0.5, family_min_peakedness=0.5, biography_min=0.7
)


def _choice(label: str, confidence: float = 0.9) -> SystemOneAnswer:
    return SystemOneAnswer(
        type="choice",
        choice=label,
        confidence=confidence,
        probabilities={label: confidence},
    )


def _ok(act: str, family: str, biography: float, *, act_conf=0.9, fam_conf=0.9):
    return SystemOneResult(
        outcome="ok",
        model="typesafe/jev-1.13",
        latency_ms=80,
        input_tokens=50,
        answers={
            "speech_act": _choice(act, act_conf),
            "family": _choice(family, fam_conf),
            "biography": SystemOneAnswer(type="noul", noul=biography),
        },
    )


def _configurable(result: SystemOneResult, *, llm_reply: str | None = None):
    s1 = AsyncMock()
    s1.evaluate = AsyncMock(return_value=result)
    llm = AsyncMock()
    llm.complete = AsyncMock(
        return_value=llm_reply
        or '{"facts": [{"value": "prefers aisle seats", "confidence": 0.9}]}'
    )
    settings = {
        "system_one": {
            "enabled": True,
            "surfaces": {
                "speech_act": {
                    "enabled": True,
                    "act_min_peakedness": 0.5,
                    "family_min_peakedness": 0.5,
                    "biography_min": 0.7,
                }
            },
        }
    }
    return (
        {
            "system_one_client": s1,
            "openrouter_client": llm,
            "settings": settings,
            "admission_judgments": [],
        },
        s1,
        llm,
    )


async def _run(cfg, prompt="I prefer aisle seats"):
    return await gather_fact_proposals(
        cfg, agent="companion", prompt=prompt, response="Noted."
    )


async def test_timed_reminder_persists_no_fact():
    cfg, s1, llm = _configurable(_ok("reminder", "drop", 0.1))
    assert await _run(cfg, "remind me Tuesday to call Mom at 3") == []
    llm.complete.assert_not_called()


async def test_forget_vs_reminder_gold_direction():
    cfg, _, _ = _configurable(_ok("forget", "preference", 0.2))
    assert await _run(cfg, "forget that I like aisle seats") == []
    cfg, _, _ = _configurable(_ok("reminder", "drop", 0.1))
    assert await _run(cfg, "forget the dentist") == []
    assert cfg["admission_judgments"][0]["answer"] == "reminder"


async def test_durable_preference_is_admitted_and_worded_by_llm():
    cfg, _, llm = _configurable(_ok("fact", "preference", 0.95))
    facts = await _run(cfg)
    assert [(f.predicate, f.value) for f in facts] == [
        ("preference", "prefers aisle seats")
    ]
    assert facts[0].agent == "companion"
    llm.complete.assert_awaited_once()


async def test_unknown_label_is_drop():
    cfg, _, llm = _configurable(_ok("banana", "preference", 0.95))
    assert await _run(cfg) == []
    llm.complete.assert_not_called()


async def test_low_peakedness_holds_without_haiku_tiebreak():
    cfg, _, llm = _configurable(_ok("fact", "preference", 0.95, act_conf=0.2))
    assert await _run(cfg) == []
    llm.complete.assert_not_called()


async def test_even_biography_noul_holds_despite_fact_choice():
    cfg, _, llm = _configurable(_ok("fact", "preference", 0.5))
    assert await _run(cfg) == []
    llm.complete.assert_not_called()


async def test_non_keep_family_holds():
    cfg, _, _ = _configurable(_ok("fact", "mood", 0.95))
    assert await _run(cfg) == []


async def test_skip_falls_back_to_legacy_extractor_once():
    cfg, s1, llm = _configurable(SystemOneResult(outcome="skip", skip_reason="timeout"))
    llm.complete.return_value = (
        '{"speech_act":"fact","family":"preference",'
        '"facts":[{"value":"aisle","confidence":0.9}]}'
    )
    facts = await _run(cfg)
    assert [f.value for f in facts] == ["aisle"]
    llm.complete.assert_awaited_once()
    assert cfg["admission_judgments"][0]["skip_reason"] == "timeout"


async def test_trivial_turn_does_not_call_system_one():
    cfg, s1, _ = _configurable(_ok("fact", "preference", 0.95))
    assert await _run(cfg, "thanks!") == []
    s1.evaluate.assert_not_called()


async def test_surface_off_uses_legacy_path_without_calling_system_one():
    cfg, s1, llm = _configurable(_ok("fact", "preference", 0.95))
    cfg["settings"]["system_one"]["surfaces"] = {}
    llm.complete.return_value = '{"speech_act":"drop","family":"drop","facts":[]}'
    assert await _run(cfg) == []
    s1.evaluate.assert_not_called()
    llm.complete.assert_awaited_once()


async def test_trace_marks_only_consumed_judgments():
    cfg, _, _ = _configurable(_ok("fact", "preference", 0.95))
    await _run(cfg)
    rows = {j["question_id"]: j for j in cfg["admission_judgments"]}
    assert set(rows) == {"speech_act", "family", "biography"}
    assert all(r["consumed"] for r in rows.values())
    cfg, _, _ = _configurable(_ok("reminder", "preference", 0.95))
    await _run(cfg)
    rows = {j["question_id"]: j for j in cfg["admission_judgments"]}
    assert rows["speech_act"]["consumed"] is True
    assert rows["family"]["consumed"] is False
    assert rows["biography"]["consumed"] is False


def test_thresholds_require_explicit_numbers():
    assert thresholds_from_settings({"system_one": {"enabled": True}}) is None
    partial = {
        "system_one": {
            "enabled": True,
            "surfaces": {"speech_act": {"enabled": True, "act_min_peakedness": 0.5}},
        }
    }
    assert thresholds_from_settings(partial) is None
    full = {
        "system_one": {
            "enabled": True,
            "surfaces": {
                "speech_act": {
                    "enabled": True,
                    "act_min_peakedness": 0.5,
                    "family_min_peakedness": 0.4,
                    "biography_min": 0.7,
                }
            },
        }
    }
    assert thresholds_from_settings(full) == AdmissionThresholds(0.5, 0.4, 0.7)
    off = {"system_one": {"enabled": False, "surfaces": full["system_one"]["surfaces"]}}
    assert thresholds_from_settings(off) is None


async def test_state_is_user_and_capped_assistant_only():
    cfg, s1, _ = _configurable(_ok("drop", "drop", 0.1))
    await gather_fact_proposals(
        cfg, agent="companion", prompt="I prefer aisle seats", response="x" * 5000
    )
    state, questions = s1.evaluate.await_args.args
    assert set(state) == {"user", "assistant"}
    assert len(state["assistant"]) == 1000
    assert list(questions) == ["speech_act", "family", "biography"]


def test_question_option_sets_are_the_closed_sets_in_stable_order():
    from ze_memory.extractor import KEEP_FAMILIES
    from ze_memory.speech_act_gate import build_questions
    from ze_memory.types import SpeechAct

    questions = build_questions()
    assert list(questions["speech_act"].criteria) == [a.value for a in SpeechAct]
    family_options = list(questions["family"].criteria)
    assert set(family_options) == set(KEEP_FAMILIES) | {"drop"}
    assert family_options[-1] == "drop"
    assert questions["biography"].type == "noul"
    assert "lembra-me" in questions["speech_act"].criteria["reminder"]


@pytest.mark.parametrize(
    "act", ["forget", "reminder", "loop", "goal", "ingest", "drop", "clarify"]
)
async def test_every_non_fact_act_persists_nothing(act):
    cfg, _, llm = _configurable(_ok(act, "preference", 0.99))
    assert await _run(cfg) == []
    llm.complete.assert_not_called()
