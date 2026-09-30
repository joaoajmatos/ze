"""MessageTrace.judgments — empty default and consumed flag."""

from __future__ import annotations

from dataclasses import asdict

from types import SimpleNamespace

from ze_core.conversation.messages.types import JudgmentTrace, MessageTrace
from ze_core.orchestration.nodes.trace import record_trace


def test_judgments_default_empty():
    trace = MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.1,
        is_compound=False,
        subtasks=["companion"],
    )
    assert trace.judgments == []


def test_two_judgments_one_consumed_asdict_round_trip():
    trace = MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.1,
        is_compound=False,
        subtasks=["companion"],
        judgments=[
            JudgmentTrace(
                question_id="speech_act",
                kind="choice",
                answer="fact",
                probabilities={"fact": 0.8, "drop": 0.2},
                peakedness=0.7,
                model="typesafe/jev-1.13-20260917",
                input_tokens=40,
                latency_ms=90,
                consumed=True,
            ),
            JudgmentTrace(
                question_id="biography",
                kind="noul",
                answer=0.4,
                latency_ms=90,
                consumed=False,
            ),
        ],
    )
    dumped = asdict(trace)
    consumed = [j["consumed"] for j in dumped["judgments"]]
    assert consumed.count(True) == 1
    assert consumed.count(False) == 1
    restored = dumped["judgments"]
    assert restored[0]["question_id"] == "speech_act"
    assert restored[1]["consumed"] is False


def _envelope():
    return SimpleNamespace(
        primary_agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.2,
        is_compound=False,
        subtasks=[],
    )


async def test_record_trace_copies_judgments_including_skip():
    skip = JudgmentTrace(
        question_id="speech_act",
        kind="choice",
        latency_ms=5,
        skip_reason="timeout",
        consumed=False,
    )
    used = JudgmentTrace(
        question_id="keep",
        kind="noul",
        answer=0.91,
        latency_ms=80,
        consumed=True,
    )
    result = await record_trace(
        {
            "envelope": _envelope(),
            "agent_result": None,
            "judgments": [skip, used],
        },
        {"configurable": {}},
    )
    judgments = result["message_trace"].judgments
    assert len(judgments) == 2
    assert judgments[0].skip_reason == "timeout"
    assert judgments[0].answer is None
    assert judgments[1].consumed is True
    assert judgments[1].answer == 0.91


async def test_record_trace_empty_when_no_evaluate():
    result = await record_trace(
        {"envelope": _envelope(), "agent_result": None},
        {"configurable": {}},
    )
    assert result["message_trace"].judgments == []
