"""Times every graph node for the turn's recorder (phase 187b)."""

from __future__ import annotations

import inspect
from dataclasses import asdict
from typing import Any, Callable

from langchain_core.runnables import RunnableConfig

from ze_logging import get_logger

from ze_core.telemetry import turn as clock
from ze_core.telemetry.turn import current_turn_telemetry

log = get_logger(__name__)


def _accepts_config(fn: Callable) -> bool:
    try:
        return "config" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def timed(name: str, fn: Callable) -> Callable:
    """Wrap a graph node so its start offset and duration reach the turn recorder.

    The wrapper records in `finally`, so a node that pauses for a confirmation
    (`GraphInterrupt`) or raises still leaves its stage. With no recorder it only
    calls the node.
    """
    pass_config = _accepts_config(fn)

    async def node(state: Any, config: RunnableConfig) -> Any:
        telemetry = current_turn_telemetry.get()
        started = clock.monotonic()
        try:
            result = fn(state, config) if pass_config else fn(state)
            if inspect.isawaitable(result):
                result = await result
            return result
        finally:
            if telemetry is not None:
                _record(telemetry, name, started, clock.monotonic())

    node.__name__ = name
    return node


def _record(telemetry: Any, name: str, started: float, ended: float) -> None:
    try:
        stage = telemetry.record_stage(name, started, ended)
        if stage is not None:
            telemetry.emit({"stages": [asdict(stage)]})
    except Exception as exc:
        log.warning("turn_telemetry_failed", method="timed", error=str(exc))


def add_timed_node(builder: Any, name: str, fn: Callable) -> None:
    builder.add_node(name, timed(name, fn))
