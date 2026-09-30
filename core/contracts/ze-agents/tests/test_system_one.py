"""Tests for SystemOneClient protocol and request/result dataclasses."""

from __future__ import annotations

from ze_agents.client import LLMClient
from ze_agents.system_one import (
    SystemOneAnswer,
    SystemOneClient,
    SystemOneQuestion,
    SystemOneResult,
)


def test_noul_question_wire_type():
    q = SystemOneQuestion(type="noul", instructions="Is this a bug?")
    assert q.type == "noul"
    assert q.to_wire() == {"type": "noul", "instructions": "Is this a bug?"}


def test_choice_and_score_questions():
    choice = SystemOneQuestion(
        type="choice",
        instructions="Which agent?",
        criteria={"calendar": "events", "companion": "chat"},
    )
    score = SystemOneQuestion(
        type="score",
        instructions="How urgent?",
        criteria=["Can wait", "This week", "Blocking"],
    )
    assert choice.to_wire()["criteria"]["calendar"] == "events"
    assert score.to_wire()["criteria"][2] == "Blocking"


def test_ok_result_exposes_noul_without_json_parsing():
    result = SystemOneResult(
        outcome="ok",
        answers={"refund": SystemOneAnswer(type="noul", noul=0.9)},
    )
    assert result.answers["refund"].noul == 0.9
    assert result.skip_reason is None


def test_skip_result_is_distinct_from_ok():
    result = SystemOneResult(outcome="skip", skip_reason="timeout")
    assert result.outcome == "skip"
    assert result.answers == {}
    assert result.skip_reason == "timeout"


def test_protocol_is_not_llm_client():
    assert hasattr(SystemOneClient, "evaluate")
    assert not hasattr(LLMClient, "evaluate")


class _FakeSystemOne:
    async def evaluate(self, state, questions):
        return SystemOneResult(outcome="ok")


def test_runtime_checkable_protocol():
    assert isinstance(_FakeSystemOne(), SystemOneClient)
