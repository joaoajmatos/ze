"""Per-turn telemetry recorder (phase 187b). The bodies arrive with lane `recorder`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from ze_core.conversation.messages.types import (
    MessageTrace,
    ModelUsage,
    StageTiming,
    TurnUsage,
)

__all__ = [
    "ModelUsage",
    "StageTiming",
    "TurnTelemetry",
    "TurnTelemetryRegistry",
    "TurnUsage",
    "current_turn_telemetry",
]

EmitFn = Callable[[dict[str, Any]], None]
SendFn = Callable[[dict[str, Any]], Awaitable[None]]


class TurnTelemetry:
    """Measures one turn on the server and stamps the result onto its MessageTrace."""

    def __init__(self, *, partial: bool = False) -> None:
        self.partial = partial
        self.emit: EmitFn | None = None

    def record_stage(self, name: str, started: float, ended: float) -> None:
        """Record one graph node; both times are `time.monotonic()` seconds."""

    def record_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        audio_seconds: float | None = None,
    ) -> None:
        """Add one model call to the turn's usage; transcription rows are skipped."""

    def stamp(self, trace: MessageTrace, main_model: str | None = None) -> MessageTrace:
        return trace


class TurnTelemetryRegistry:
    """One recorder per running turn, keyed by thread id."""

    def start(self, thread_id: str) -> TurnTelemetry:
        return TurnTelemetry()

    def resume(self, thread_id: str) -> TurnTelemetry:
        return TurnTelemetry(partial=True)

    def finish(self, thread_id: str) -> None:
        return None


current_turn_telemetry: ContextVar[TurnTelemetry | None] = ContextVar(
    "current_turn_telemetry", default=None
)
