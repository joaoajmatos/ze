"""gather_fact_proposals with the System One speech-act surface (163)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ze_memory.extractor import _SYSTEM, gather_fact_proposals
from ze_memory.speech_act_judge import SPEECH_ACT_QUESTIONS, build_state
from tests.fixtures.speech_act_gold import (
    GOAL,
    LOOP,
    PERSIST,
    REMINDER,
    FakeSystemOneClient,
)

_SETTINGS = {
    "system_one": {
        "surfaces": {
            "speech_act": {"enabled": True, "choice_hold": 0.6, "biography_hold": 0.7}
        }
    }
}


def _configurable(result, complete_return='{"facts": [{"value": "prefers aisle seats"}]}'):
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=complete_return)
    fake = FakeSystemOneClient(result)
    return (
        {"openrouter_client": llm, "settings": _SETTINGS, "system_one_client": fake},
        llm,
        fake,
    )


async def _gather(turn, configurable):
    return await gather_fact_proposals(
        configurable, agent="companion", prompt=turn.user, response=turn.assistant
    )


@pytest.mark.parametrize("turn", REMINDER + LOOP + GOAL, ids=lambda t: t.id)
async def test_non_fact_turns_write_nothing_and_make_no_generative_call(turn):
    configurable, llm, _ = _configurable(turn.result())
    admission = await _gather(turn, configurable)
    assert admission.facts == []
    assert admission.path == "system_one"
    assert admission.judgment is not None
    llm.complete.assert_not_awaited()


@pytest.mark.parametrize("turn", [t for t in PERSIST if t.family == "preference"], ids=lambda t: t.id)
async def test_persist_uses_value_writer_with_system_one_family(turn):
    configurable, llm, _ = _configurable(turn.result())
    admission = await _gather(turn, configurable)
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.kwargs["system"] != _SYSTEM
    assert [(f.predicate, f.value, f.confidence, f.agent) for f in admission.facts] == [
        ("preference", "prefers aisle seats", 0.8, "companion")
    ]
    assert admission.path == "system_one"
    assert admission.consumed == frozenset({"speech_act", "family", "biography"})
    assert admission.question_ids == ("speech_act", "family", "biography")


async def test_value_writer_family_and_act_keys_are_ignored():
    turn = PERSIST[0]
    configurable, _, _ = _configurable(
        turn.result(),
        '{"speech_act": "drop", "family": "constraint", "facts": [{"value": "aisle"}]}',
    )
    admission = await _gather(turn, configurable)
    assert [f.predicate for f in admission.facts] == ["preference"]


@pytest.mark.parametrize(
    "returned", ["not json", '{"facts": []}', '{"facts": [{"value": ""}]}']
)
async def test_value_writer_unusable_output_persists_nothing_without_second_call(returned):
    turn = PERSIST[0]
    configurable, llm, _ = _configurable(turn.result(), returned)
    admission = await _gather(turn, configurable)
    assert admission.facts == []
    assert admission.path == "system_one"
    llm.complete.assert_awaited_once()


async def test_value_writer_exception_persists_nothing_without_fallback():
    turn = PERSIST[0]
    configurable, llm, _ = _configurable(turn.result())
    llm.complete = AsyncMock(side_effect=RuntimeError("boom"))
    admission = await _gather(turn, configurable)
    assert admission.facts == []
    llm.complete.assert_awaited_once()


async def test_client_called_once_with_single_attempt_and_minimal_state():
    turn = PERSIST[0]
    configurable, _, fake = _configurable(turn.result())
    await _gather(turn, configurable)
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["max_attempts"] == 1
    assert call["state"] == build_state(turn.user, turn.assistant)
    assert call["questions"] is SPEECH_ACT_QUESTIONS


# ── US2: cancel language is not forget-biography ─────────────────────────────

from tests.fixtures.speech_act_gold import AISLE_RETRACT, DENTIST_CANCEL  # noqa: E402


@pytest.mark.parametrize("turn", DENTIST_CANCEL, ids=lambda t: t.id)
async def test_dentist_cancel_is_reminder_and_writes_nothing(turn):
    configurable, llm, _ = _configurable(turn.result())
    admission = await _gather(turn, configurable)
    assert turn.act == "reminder"
    assert admission.judgment.answers["speech_act"].choice == "reminder"
    assert admission.facts == []
    assert admission.consumed == frozenset({"speech_act"})
    llm.complete.assert_not_awaited()


@pytest.mark.parametrize("turn", AISLE_RETRACT, ids=lambda t: t.id)
async def test_aisle_retract_is_forget_and_writes_nothing(turn):
    configurable, llm, _ = _configurable(turn.result())
    admission = await _gather(turn, configurable)
    assert admission.judgment.answers["speech_act"].choice == "forget"
    assert admission.facts == []
    assert admission.consumed == frozenset({"speech_act"})
    llm.complete.assert_not_awaited()


def _criteria(label: str) -> str:
    return SPEECH_ACT_QUESTIONS["speech_act"].criteria[label].lower()


def test_forget_criterion_encodes_cancel_versus_retract_rule():
    text = _criteria("forget")
    assert "reminder, loop or goal" in text
    assert "cancel" in text
    assert "esquece que prefiro" in text


def test_reminder_criterion_owns_cancelling_a_ping_with_pt_example():
    text = _criteria("reminder")
    assert "cancel" in text
    assert "esquece o dentista" in text


@pytest.mark.parametrize("label", ["loop", "goal"])
def test_loop_and_goal_criteria_own_abandoning_them(label):
    text = _criteria(label)
    assert any(word in text for word in ("abandon", "drop", "cancel"))


async def test_unknown_label_from_client_is_dropped_not_persisted():
    turn = PERSIST[0]
    result = turn.result()
    result.answers["speech_act"].choice = "remind"
    configurable, llm, _ = _configurable(result)
    admission = await _gather(turn, configurable)
    assert admission.facts == []
    llm.complete.assert_not_awaited()


# ── US3: unsure holds; skip runs one Haiku judge ─────────────────────────────

import logging  # noqa: E402

from ze_agents.system_one import SystemOneResult  # noqa: E402
from tests.fixtures.speech_act_gold import make_result  # noqa: E402

_HAIKU_JSON = (
    '{"speech_act": "fact", "family": "preference", '
    '"facts": [{"value": "aisle seats"}]}'
)


@pytest.mark.parametrize(
    "result",
    [
        make_result("fact", "preference", act_confidence=0.3),
        make_result("fact", "preference", family_confidence=0.3),
        make_result("fact", "preference", noul=0.5),
        make_result("fact", "drop"),
    ],
    ids=["act_unsure", "family_unsure", "noul_even", "family_drop"],
)
async def test_hold_makes_no_generative_call_and_no_tie_break(result):
    configurable, llm, _ = _configurable(result)
    admission = await _gather(PERSIST[0], configurable)
    assert admission.facts == []
    assert admission.path == "system_one"
    llm.complete.assert_not_awaited()


@pytest.mark.parametrize("reason", ["timeout", "overload", "missing_key", "disabled"])
async def test_client_skip_runs_exactly_one_haiku_judge(reason):
    skip = SystemOneResult(outcome="skip", skip_reason=reason, latency_ms=12)
    configurable, llm, _ = _configurable(skip, _HAIKU_JSON)
    admission = await _gather(PERSIST[0], configurable)
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.kwargs["system"] == _SYSTEM
    assert admission.path == "haiku"
    assert admission.judgment is skip
    assert admission.consumed == frozenset()
    assert admission.question_ids == ("speech_act", "family", "biography")
    assert admission.skip_reason == reason
    assert [f.value for f in admission.facts] == ["aisle seats"]


async def test_invalid_answer_runs_one_haiku_judge_and_records_reason():
    result = make_result("fact", "preference")
    result.answers.pop("biography")
    configurable, llm, _ = _configurable(result, _HAIKU_JSON)
    admission = await _gather(PERSIST[0], configurable)
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.kwargs["system"] == _SYSTEM
    assert admission.path == "haiku"
    assert admission.skip_reason == "invalid_answer"
    assert admission.judgment is result
    assert admission.consumed == frozenset()


async def test_uncalibrated_surface_skips_client_and_warns(caplog):
    settings = {
        "system_one": {
            "surfaces": {
                "speech_act": {"enabled": True, "choice_hold": None, "biography_hold": 0.7}
            }
        }
    }
    configurable, llm, fake = _configurable(PERSIST[0].result(), _HAIKU_JSON)
    configurable["settings"] = settings
    with caplog.at_level(logging.WARNING):
        admission = await _gather(PERSIST[0], configurable)
    assert fake.calls == []
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.kwargs["system"] == _SYSTEM
    assert admission.path == "haiku"
    assert admission.skip_reason == "uncalibrated"
    assert admission.judgment is None


async def test_calibrated_but_no_system_one_client_uses_haiku():
    configurable, llm, _ = _configurable(PERSIST[0].result(), _HAIKU_JSON)
    del configurable["system_one_client"]
    admission = await _gather(PERSIST[0], configurable)
    assert admission.path == "haiku"
    assert admission.judgment is None
    llm.complete.assert_awaited_once()
