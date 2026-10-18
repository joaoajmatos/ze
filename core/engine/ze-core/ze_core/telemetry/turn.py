"""Per-turn telemetry recorder (phase 187b).

One `TurnTelemetry` measures a running turn on the server and stamps the result onto
the reply's `MessageTrace` before anyone saves or sends it. It lives in a registry
keyed by thread id, so it outlives a confirmation pause. Telemetry never raises into
a turn: every method logs `turn_telemetry_failed` and carries on.
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any

from ze_logging import get_logger

from ze_core.openrouter.context_windows import (
    MODEL_CONTEXT_WINDOWS,
    get_context_window,
)
from ze_core.telemetry.pricing import MODEL_PRICING, estimate_cost_usd
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

log = get_logger(__name__)

SEND_TIMEOUT_S = 1.0
DRAIN_TIMEOUT_S = 1.0
ENTRY_MAX_AGE_S = 30 * 60

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


def monotonic() -> float:
    return time.monotonic()


def wall() -> float:
    return time.time()


def _guarded(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def inner(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(self, *args, **kwargs)
        except Exception as exc:
            log.warning("turn_telemetry_failed", method=fn.__name__, error=str(exc))
            return None

    return inner


@dataclass
class _ModelAccumulator:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    max_prompt_tokens: int = 0


# A price-table key ending in "-" is a version-agnostic prefix: the System One models.
_SYSTEM_ONE_PREFIXES = tuple(slug for slug in MODEL_PRICING if slug.endswith("-"))


def _is_system_one(model: str) -> bool:
    return model.startswith(_SYSTEM_ONE_PREFIXES)


def _is_priced(model: str) -> bool:
    return model in MODEL_PRICING or _is_system_one(model)


class TurnTelemetry:
    """Measures one turn on the server and stamps the result onto its MessageTrace."""

    def __init__(self, *, partial: bool = False) -> None:
        self.partial = partial
        self.started = monotonic()
        self.started_wall = wall()  # display only
        self.stages: list[StageTiming] = []
        self.run = 1
        self.paused_ms = 0
        self._paused_at: float | None = None
        self.models: dict[str, _ModelAccumulator] = {}
        self._frozen = False
        self._send: SendFn | None = None
        self._queue: asyncio.Queue[dict[str, Any] | None] | None = None
        self._worker: asyncio.Task[None] | None = None
        self._closed = False

    @_guarded
    def record_stage(
        self, name: str, started: float, ended: float
    ) -> StageTiming | None:
        """Record one graph node; both times are `time.monotonic()` seconds."""
        if self._frozen:
            return None
        stage = StageTiming(
            name=name,
            start_ms=max(0, round((started - self.started) * 1000)),
            duration_ms=max(0, round((ended - started) * 1000)),
            run=self.run,
        )
        self.stages.append(stage)
        return stage

    @_guarded
    def record_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        audio_seconds: float | None = None,
    ) -> None:
        """Add one model call to the turn's usage; transcription rows are skipped."""
        if self._frozen or audio_seconds is not None:
            return
        row = self.models.setdefault(model, _ModelAccumulator())
        row.calls += 1
        row.prompt_tokens += prompt_tokens
        row.completion_tokens += completion_tokens
        row.max_prompt_tokens = max(row.max_prompt_tokens, prompt_tokens)

    def _usage(self, main_model: str | None) -> TurnUsage | None:
        if not self.models:
            return None
        rows = [
            ModelUsage(
                model=model,
                calls=acc.calls,
                prompt_tokens=acc.prompt_tokens,
                completion_tokens=acc.completion_tokens,
                max_prompt_tokens=acc.max_prompt_tokens,
                cost_usd=estimate_cost_usd(
                    model, acc.prompt_tokens, acc.completion_tokens
                ),
                estimated=not _is_priced(model),
            )
            for model, acc in self.models.items()
        ]
        system_one_tokens = sum(
            r.prompt_tokens + r.completion_tokens
            for r in rows
            if _is_system_one(r.model)
        )
        main = None if main_model and _is_system_one(main_model) else main_model
        window = get_context_window(main) if main else None
        main_row = next((r for r in rows if r.model == main), None)
        fill = (
            main_row.max_prompt_tokens / window
            if main_row is not None and window
            else None
        )
        window_estimated = main is not None and main not in MODEL_CONTEXT_WINDOWS
        return TurnUsage(
            main_model=main,
            models=rows,
            context_fill=fill,
            context_window=window,
            estimated=any(r.estimated for r in rows) or window_estimated,
            system_one_tokens=system_one_tokens,
        )

    @_guarded
    def pause(self) -> None:
        """The run returned interrupted: the clock for `paused_ms` starts."""
        self._paused_at = monotonic()

    @_guarded
    def begin_resumed_run(self) -> None:
        if self._paused_at is not None:
            self.paused_ms += round((monotonic() - self._paused_at) * 1000)
            self._paused_at = None
        self.run += 1

    def stamp(self, trace: MessageTrace, main_model: str | None = None) -> MessageTrace:
        """Freeze the recorder and return `trace` with the turn's measurements."""
        try:
            self._frozen = True
            return replace(
                trace,
                stages=list(self.stages),
                turn_duration_ms=round((monotonic() - self.started) * 1000),
                paused_ms=self.paused_ms,
                usage=self._usage(main_model),
                telemetry_partial=self.partial,
            )
        except Exception as exc:
            log.warning("turn_telemetry_failed", method="stamp", error=str(exc))
            return trace

    # Sending. Frames are best effort: a slow or displaced client never delays a node.

    def set_send(self, send: SendFn | None) -> None:
        self._send = send

    @_guarded
    def emit(self, fields: dict[str, Any]) -> None:
        if self._send is None or self._closed:
            return
        if self._queue is None:
            self._queue = asyncio.Queue()
        if self._worker is None or self._worker.done():
            self._worker = asyncio.get_running_loop().create_task(self._run())
        self._queue.put_nowait(fields)

    async def _run(self) -> None:
        assert self._queue is not None
        while True:
            fields = await self._queue.get()
            try:
                if fields is None:
                    return
                send = self._send
                if send is None:
                    continue
                try:
                    await asyncio.wait_for(send(fields), SEND_TIMEOUT_S)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning(
                        "turn_telemetry_frame_dropped",
                        error=str(exc) or type(exc).__name__,
                    )
            finally:
                self._queue.task_done()

    async def drain(self) -> None:
        """Wait for queued frames, at most `DRAIN_TIMEOUT_S` in total; drop the rest."""
        try:
            queue = self._queue
            if queue is None or self._worker is None or self._worker.done():
                return
            try:
                await asyncio.wait_for(queue.join(), DRAIN_TIMEOUT_S)
            except asyncio.TimeoutError:
                dropped = 0
                while not queue.empty():
                    queue.get_nowait()
                    queue.task_done()
                    dropped += 1
                log.warning("turn_telemetry_drain_timeout", dropped=dropped)
                self._worker.cancel()
        except Exception as exc:
            log.warning("turn_telemetry_failed", method="drain", error=str(exc))

    async def close(self) -> None:
        """Stop the sender; later `emit` calls do nothing."""
        self._closed = True
        worker = self._worker
        if worker is None or worker.done():
            return
        worker.cancel()
        try:
            await worker
        except (asyncio.CancelledError, Exception):
            pass


class TurnTelemetryRegistry:
    """One recorder per running turn, keyed by thread id."""

    def __init__(self) -> None:
        self._entries: dict[str, TurnTelemetry] = {}

    def start(self, thread_id: str) -> TurnTelemetry:
        now = monotonic()
        for key in [
            k for k, t in self._entries.items() if now - t.started > ENTRY_MAX_AGE_S
        ]:
            self._drop(key)
        self._drop(thread_id)
        telemetry = TurnTelemetry()
        self._entries[thread_id] = telemetry
        return telemetry

    def resume(self, thread_id: str) -> TurnTelemetry:
        telemetry = self._entries.get(thread_id)
        if telemetry is None:
            telemetry = TurnTelemetry(partial=True)
            self._entries[thread_id] = telemetry
            return telemetry
        telemetry.begin_resumed_run()
        return telemetry

    def finish(self, thread_id: str) -> None:
        self._drop(thread_id)

    def _drop(self, thread_id: str) -> None:
        telemetry = self._entries.pop(thread_id, None)
        if telemetry is None:
            return
        telemetry._closed = True
        worker = telemetry._worker
        if worker is not None and not worker.done():
            worker.cancel()


current_turn_telemetry: ContextVar[TurnTelemetry | None] = ContextVar(
    "current_turn_telemetry", default=None
)
