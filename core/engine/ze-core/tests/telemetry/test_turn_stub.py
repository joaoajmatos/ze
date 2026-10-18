from __future__ import annotations

from dataclasses import replace

from ze_core.conversation.messages.types import MessageTrace
from ze_core.telemetry.turn import (
    ModelUsage,
    StageTiming,
    TurnTelemetry,
    TurnTelemetryRegistry,
    TurnUsage,
    current_turn_telemetry,
)


def _trace() -> MessageTrace:
    return MessageTrace(
        agent="a",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
    )


def test_every_name_imports_and_the_stub_stamps_nothing():
    registry = TurnTelemetryRegistry()
    telemetry = registry.start("t1")
    telemetry.record_stage("embed_route", 1.0, 2.0)
    telemetry.record_call("m", 1, 1)
    trace = _trace()
    assert telemetry.stamp(trace, "m") == replace(trace)
    assert registry.resume("t1") is not None
    registry.finish("t1")
    assert current_turn_telemetry.get() is None
    assert all([StageTiming, ModelUsage, TurnUsage, TurnTelemetry])


def test_container_has_a_registry():
    from ze_core.container import Container

    container = Container(
        settings=None,
        pool=None,
        checkpointer_pool=None,
        embedder=None,
        openrouter_client=None,
        router=None,
        memory_store=None,
        memory_consolidator=None,
        graph=None,
    )
    assert isinstance(container.turn_telemetry, TurnTelemetryRegistry)
