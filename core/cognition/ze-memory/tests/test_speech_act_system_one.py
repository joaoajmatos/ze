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
