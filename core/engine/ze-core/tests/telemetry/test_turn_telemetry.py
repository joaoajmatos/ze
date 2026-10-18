from __future__ import annotations

import asyncio
import time
from dataclasses import replace

import pytest

from ze_core.conversation.messages.types import MessageTrace
from ze_core.telemetry import turn as turn_mod
from ze_core.telemetry.turn import TurnTelemetry, TurnTelemetryRegistry


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(turn_mod, "monotonic", fake)
    # A wall-clock jump must change nothing.
    monkeypatch.setattr(turn_mod, "wall", lambda: 5_000_000.0)
    return fake


def _trace() -> MessageTrace:
    return MessageTrace(
        agent="a",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
    )


def test_record_stage_uses_monotonic_offsets(clock):
    t0 = clock.now
    telemetry = TurnTelemetry()
    telemetry.record_stage("fetch_context", t0 + 0.2, t0 + 0.288)
    stage = telemetry.stages[0]
    assert (stage.name, stage.start_ms, stage.duration_ms, stage.run) == (
        "fetch_context",
        200,
        88,
        1,
    )


def test_wall_clock_change_changes_nothing(clock, monkeypatch):
    t0 = clock.now
    telemetry = TurnTelemetry()
    monkeypatch.setattr(turn_mod, "wall", lambda: 1.0)
    telemetry.record_stage("x", t0 + 1.0, t0 + 1.5)
    assert (telemetry.stages[0].start_ms, telemetry.stages[0].duration_ms) == (
        1000,
        500,
    )


def test_pause_then_resume_adds_gap_and_bumps_run(clock):
    registry = TurnTelemetryRegistry()
    telemetry = registry.start("t1")
    telemetry.pause()
    clock.now += 20
    again = registry.resume("t1")
    assert again is telemetry
    assert telemetry.paused_ms == 20000
    assert telemetry.run == 2
    telemetry.record_stage("execute_tool", clock.now, clock.now + 1)
    assert telemetry.stages[0].run == 2
    assert telemetry.partial is False


def test_resume_without_recorder_is_partial_and_has_no_send(clock):
    registry = TurnTelemetryRegistry()
    telemetry = registry.resume("ghost")
    assert telemetry.partial is True
    telemetry.emit({"stages": []})  # no send target: a no-op, never raises
    stamped = telemetry.stamp(_trace())
    assert stamped.telemetry_partial is True


def test_stamp_freezes_the_recorder(clock):
    telemetry = TurnTelemetry()
    t0 = clock.now
    telemetry.record_stage("a", t0, t0 + 0.1)
    clock.now += 2
    stamped = telemetry.stamp(_trace())
    telemetry.record_stage("late", clock.now, clock.now + 1)
    telemetry.record_call("m", 10, 10)
    assert [s.name for s in stamped.stages] == ["a"]
    assert [s.name for s in telemetry.stages] == ["a"]
    assert stamped.turn_duration_ms == 2000
    assert stamped.paused_ms == 0
    assert stamped.telemetry_partial is False
    assert telemetry.stamp(replace(stamped, stages=[])).stages == [
        s for s in stamped.stages
    ]


async def test_drain_returns_when_queue_is_empty(clock):
    sent: list[dict] = []

    async def send(fields):
        sent.append(fields)

    telemetry = TurnTelemetry()
    telemetry.set_send(send)
    telemetry.emit({"stages": [1]})
    telemetry.emit({"stages": [2]})
    await telemetry.drain()
    assert sent == [{"stages": [1]}, {"stages": [2]}]
    await telemetry.close()


async def test_drain_is_bounded_and_drops_what_is_left(clock, monkeypatch):
    monkeypatch.setattr(turn_mod, "SEND_TIMEOUT_S", 5.0)
    monkeypatch.setattr(turn_mod, "DRAIN_TIMEOUT_S", 0.05)

    async def never(fields):
        await asyncio.Event().wait()

    telemetry = TurnTelemetry()
    telemetry.set_send(never)
    for i in range(3):
        telemetry.emit({"stages": [i]})
    started = time.perf_counter()
    await telemetry.drain()
    assert time.perf_counter() - started < 0.5
    await telemetry.close()


async def test_emit_does_not_await_the_send(clock, monkeypatch):
    monkeypatch.setattr(turn_mod, "SEND_TIMEOUT_S", 0.05)
    sent = 0

    async def never(fields):
        nonlocal sent
        sent += 1
        await asyncio.Event().wait()

    telemetry = TurnTelemetry()
    telemetry.set_send(never)
    started = time.perf_counter()
    for i in range(17):
        telemetry.emit({"stages": [i]})
    assert time.perf_counter() - started < 0.05
    # Each stuck frame is dropped after the timeout and the next one goes out.
    await asyncio.sleep(0.3)
    assert sent >= 3
    await telemetry.close()


async def test_frames_go_out_in_order_and_close_stops_the_sender(clock):
    sent: list[int] = []

    async def send(fields):
        sent.append(fields["n"])

    telemetry = TurnTelemetry()
    telemetry.set_send(send)
    for n in range(5):
        telemetry.emit({"n": n})
    await telemetry.drain()
    assert sent == [0, 1, 2, 3, 4]
    await telemetry.close()
    telemetry.emit({"n": 99})
    await asyncio.sleep(0.01)
    assert sent == [0, 1, 2, 3, 4]


async def test_a_send_that_raises_is_dropped_and_the_next_goes_out(clock):
    sent: list[int] = []

    async def send(fields):
        if fields["n"] == 0:
            raise RuntimeError("socket gone")
        sent.append(fields["n"])

    telemetry = TurnTelemetry()
    telemetry.set_send(send)
    telemetry.emit({"n": 0})
    telemetry.emit({"n": 1})
    await telemetry.drain()
    assert sent == [1]
    await telemetry.close()


def test_start_drops_old_entries_and_finish_removes(clock):
    registry = TurnTelemetryRegistry()
    old = registry.start("old")
    clock.now += 31 * 60
    registry.start("new")
    assert registry.resume("old") is not old
    registry.finish("new")
    assert registry.resume("new").partial is True


def test_start_replaces_an_entry_for_the_same_thread(clock):
    registry = TurnTelemetryRegistry()
    first = registry.start("t")
    second = registry.start("t")
    assert first is not second
    assert registry.resume("t") is second


def test_every_method_swallows_internal_errors(clock, monkeypatch):
    telemetry = TurnTelemetry()
    monkeypatch.setattr(
        turn_mod, "monotonic", lambda: (_ for _ in ()).throw(ValueError("boom"))
    )
    telemetry.record_stage("a", 1.0, 2.0)
    telemetry.record_call("m", 1, 1)
    telemetry.pause()
    trace = _trace()
    assert telemetry.stamp(trace) is trace


def test_emit_raising_does_not_propagate(clock):
    telemetry = TurnTelemetry()
    telemetry.set_send(lambda fields: (_ for _ in ()).throw(RuntimeError("x")))
    telemetry.emit({"a": 1})  # no running loop: logged, swallowed
