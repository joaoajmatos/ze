"""WS /scripts frame contract (specs/phases/197-programmatic-tool-use/contracts/scripts.md).

Builders for every frame, and `FakeScriptSidecar`: an in-memory stand-in for the
sidecar socket that plays scripted frames and records what Ze sent. The runner
(T023) and the sidecar tests share these shapes so the two sides cannot drift.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

END_STATUSES = (
    "ok",
    "exception",
    "timeout",
    "killed",
    "bad_request",
    "busy",
    "unavailable",
    "resource_limit",
)
WS_MAX_SIZE = 2 * 1024 * 1024


def start_frame(
    script_id: str, source: str, stub: str, timeout_seconds: int = 30
) -> dict[str, Any]:
    return {
        "type": "start",
        "id": script_id,
        "source": source,
        "stub": stub,
        "timeout_seconds": timeout_seconds,
    }


def call_frame(seq: int, tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "call", "seq": seq, "tool": tool, "args": args or {}}


def reply_frame(
    seq: int, *, ok: bool = True, value: Any = None, error: str | None = None
) -> dict[str, Any]:
    frame: dict[str, Any] = {"type": "reply", "seq": seq, "ok": ok}
    if ok:
        frame["value"] = value
    else:
        frame["error"] = error or "error"
    return frame


def cancel_frame() -> dict[str, Any]:
    return {"type": "cancel"}


def end_frame(
    status: str = "ok",
    *,
    value: Any = None,
    writes: list[dict[str, Any]] | None = None,
    stderr_tail: str = "",
    exception: str | None = None,
) -> dict[str, Any]:
    if status not in END_STATUSES:
        raise ValueError(f"unknown end status {status!r}")
    return {
        "type": "end",
        "status": status,
        "value": value,
        "writes": writes or [],
        "stderr_tail": stderr_tail,
        "exception": exception,
    }


def stat_payload(*, scripts_isolated: bool = True, scripts_busy: bool = False) -> dict:
    return {"scripts_isolated": scripts_isolated, "scripts_busy": scripts_busy}


@dataclass(frozen=True)
class WaitForZe:
    """Hold the script until Ze has sent `count` frames of `type`."""

    type: str
    count: int = 1


class FakeScriptSocket:
    """The websocket the runner sees: `send`, `recv`, `close`, async iteration."""

    max_size = WS_MAX_SIZE

    def __init__(self, plan: list[dict[str, Any] | WaitForZe]) -> None:
        self._plan = list(plan)
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self._sent_event = asyncio.Event()

    async def send(self, raw: str | bytes) -> None:
        self.sent.append(json.loads(raw))
        self._sent_event.set()

    def sent_of(self, type_: str) -> list[dict[str, Any]]:
        return [f for f in self.sent if f.get("type") == type_]

    async def recv(self) -> str:
        while self._plan:
            item = self._plan.pop(0)
            if isinstance(item, WaitForZe):
                while len(self.sent_of(item.type)) < item.count:
                    self._sent_event.clear()
                    await self._sent_event.wait()
                continue
            return json.dumps(item)
        await asyncio.Event().wait()  # a sidecar that never ends the script
        raise AssertionError("unreachable")

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self) -> FakeScriptSocket:
        return self

    async def __anext__(self) -> str:
        if self.closed:
            raise StopAsyncIteration
        return await self.recv()


class FakeScriptSidecar:
    """Plays `plan` to the first connection; records the handshake."""

    def __init__(self, plan: list[dict[str, Any] | WaitForZe]) -> None:
        self.socket = FakeScriptSocket(plan)
        self.connects: list[dict[str, Any]] = []

    def connect(self, url: str, **kwargs: Any) -> _Connection:
        self.connects.append({"url": url, **kwargs})
        return _Connection(self.socket)


class _Connection:
    def __init__(self, socket: FakeScriptSocket) -> None:
        self._socket = socket

    async def __aenter__(self) -> FakeScriptSocket:
        return self._socket

    async def __aexit__(self, *exc: object) -> None:
        await self._socket.close()

    def __await__(self):
        async def _open() -> FakeScriptSocket:
            return self._socket

        return _open().__await__()
