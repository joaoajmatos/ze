from __future__ import annotations

import pytest

from ze_core.conversation.messages.types import MessageTrace
from ze_core.telemetry.pricing import estimate_cost_usd
from ze_core.telemetry.turn import TurnTelemetry

SONNET = "anthropic/claude-sonnet-4-6"


def _trace() -> MessageTrace:
    return MessageTrace(
        agent="a",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
    )


def test_two_calls_accumulate_per_model():
    t = TurnTelemetry()
    t.record_call(SONNET, 5200, 300)
    t.record_call(SONNET, 3920, 110)
    usage = t.stamp(_trace(), SONNET).usage
    assert usage is not None
    (row,) = usage.models
    assert (row.model, row.calls) == (SONNET, 2)
    assert (row.prompt_tokens, row.completion_tokens) == (9120, 410)
    assert row.max_prompt_tokens == 5200
    assert row.cost_usd == pytest.approx(estimate_cost_usd(SONNET, 9120, 410))
    assert row.estimated is False
    assert usage.main_model == SONNET
    assert usage.context_window == 200000
    assert usage.context_fill == pytest.approx(5200 / 200000)
    assert usage.estimated is False
    assert usage.system_one_tokens == 0


def test_system_one_is_counted_apart_and_never_main():
    t = TurnTelemetry()
    t.record_call(SONNET, 1000, 100)
    t.record_call("typesafe/jev-20260917", 1500, 340)
    usage = t.stamp(_trace(), SONNET).usage
    assert usage is not None
    assert usage.system_one_tokens == 1840
    assert usage.main_model == SONNET
    assert usage.context_fill == pytest.approx(1000 / 200000)


def test_system_one_never_becomes_main_even_when_alone():
    t = TurnTelemetry()
    t.record_call("typesafe/jev-20260917", 1500, 340)
    usage = t.stamp(_trace(), None).usage
    assert usage is not None
    assert usage.main_model is None
    assert usage.context_fill is None
    assert usage.system_one_tokens == 1840


def test_unknown_model_is_estimated_and_uses_the_default_window():
    t = TurnTelemetry()
    t.record_call("acme/mystery-1", 40000, 100)
    usage = t.stamp(_trace(), "acme/mystery-1").usage
    assert usage is not None
    assert usage.models[0].estimated is True
    assert usage.estimated is True
    assert usage.context_window == 32000
    assert usage.context_fill == pytest.approx(40000 / 32000)
    assert usage.context_fill > 1


def test_transcription_rows_are_not_usage():
    t = TurnTelemetry()
    t.record_call("openai/whisper-1", 0, 0, audio_seconds=12.5)
    assert t.stamp(_trace(), SONNET).usage is None


def test_no_calls_means_no_usage():
    assert TurnTelemetry().stamp(_trace(), SONNET).usage is None


def test_late_calls_after_the_stamp_are_ignored():
    t = TurnTelemetry()
    t.record_call(SONNET, 10, 10)
    stamped = t.stamp(_trace(), SONNET)
    t.record_call(SONNET, 999, 999)
    assert stamped.usage is not None
    assert stamped.usage.models[0].prompt_tokens == 10
    again = t.stamp(_trace(), SONNET)
    assert again.usage is not None and again.usage.models[0].prompt_tokens == 10


def test_stamp_leaves_tool_duration_alone():
    t = TurnTelemetry()
    trace = _trace()
    trace.tool_duration_ms = 312
    assert t.stamp(trace, SONNET).tool_duration_ms == 312
