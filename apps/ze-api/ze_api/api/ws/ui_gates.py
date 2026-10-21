"""In-process gates for screen-pressed tool actions (Phase 191a)."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ze_agents.park import ParkedWrite

_CLOSED_MEMORY = 200


@dataclass
class UiActionGate:
    request_id: str
    thread_id: str
    agent: str
    plugin: str
    tool: str
    args: dict[str, Any]
    parked: ParkedWrite
    effect: str
    frame: dict[str, Any]
    timer: asyncio.Task | None = field(default=None, repr=False)


class UiActionGates:
    """Open UI gates, in process. Lost on restart: a later `confirm` is "expired"."""

    def __init__(
        self, sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep
    ) -> None:
        self.sleep = sleep
        self._open: dict[str, UiActionGate] = {}
        self._closed: OrderedDict[str, None] = OrderedDict()

    def add(self, gate: UiActionGate) -> None:
        self._open[gate.request_id] = gate

    def pop(self, request_id: str) -> UiActionGate | None:
        gate = self._open.pop(request_id, None)
        if gate is not None:
            self._closed[request_id] = None
            while len(self._closed) > _CLOSED_MEMORY:
                self._closed.popitem(last=False)
        return gate

    def was_closed(self, request_id: str) -> bool:
        return request_id in self._closed

    def for_thread(self, thread_id: str) -> list[UiActionGate]:
        return [g for g in self._open.values() if g.thread_id == thread_id]

    def open_frames(self) -> list[dict[str, Any]]:
        return [dict(g.frame) for g in self._open.values()]
