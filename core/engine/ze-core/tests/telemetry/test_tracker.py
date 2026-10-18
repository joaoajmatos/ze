from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_core.telemetry.tracker import CostTracker
from ze_core.telemetry.turn import TurnTelemetry, current_turn_telemetry


def _record(tracker: CostTracker, **kw) -> None:
    args = dict(
        model="anthropic/claude-sonnet-4-6",
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        duration_ms=50,
    )
    args.update(kw)
    tracker.record(**args)


async def test_record_adds_to_the_current_recorder_and_still_writes():
    store = MagicMock()
    store.write = AsyncMock()
    tracker = CostTracker(store)
    telemetry = TurnTelemetry()
    token = current_turn_telemetry.set(telemetry)
    try:
        _record(tracker)
    finally:
        current_turn_telemetry.reset(token)
    assert telemetry.models["anthropic/claude-sonnet-4-6"].calls == 1
    store.write.assert_called_once()


def test_record_without_a_recorder_is_unchanged():
    tracker = CostTracker(None)
    _record(tracker)  # logs only; nothing to add to


async def test_a_recorder_that_fails_never_breaks_the_cost_record():
    store = MagicMock()
    store.write = AsyncMock()
    tracker = CostTracker(store)
    broken = MagicMock()
    broken.record_call.side_effect = RuntimeError("nope")
    token = current_turn_telemetry.set(broken)
    try:
        _record(tracker)
    finally:
        current_turn_telemetry.reset(token)
    store.write.assert_called_once()


def test_audio_rows_reach_the_recorder_and_are_skipped_there():
    tracker = CostTracker(None)
    telemetry = TurnTelemetry()
    token = current_turn_telemetry.set(telemetry)
    try:
        _record(tracker, model="openai/whisper-1", audio_seconds=3.0)
    finally:
        current_turn_telemetry.reset(token)
    assert telemetry.models == {}
