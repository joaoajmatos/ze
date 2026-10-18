from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ze_agents.scripts import (
    DispatchReply,
    ScriptLimits,
    ScriptOutcome,
    ScriptRequest,
)
from ze_logging import get_logger

from ze_workspace.client import WorkspaceClient
from ze_workspace.errors import WorkspaceUnavailableError

log = get_logger(__name__)

WS_MAX_SIZE = 2 * 1024 * 1024
_END_STATUSES = {
    "ok",
    "exception",
    "timeout",
    "killed",
    "bad_request",
    "busy",
    "unavailable",
    "resource_limit",
}


def _unavailable(reason: str) -> ScriptOutcome:
    return ScriptOutcome(status="unavailable", exception=reason)


class WorkspaceScriptRunner:
    """Runs one script over WS /scripts, serving its tool calls through `dispatch`."""

    def __init__(
        self,
        client: WorkspaceClient,
        *,
        connect: Callable[..., Any] | None = None,
        learning: Any = None,
        grace_seconds: float = 5,
    ) -> None:
        self._client = client
        self._connect = connect
        self._learning = learning
        self._grace = grace_seconds
        self.limits = ScriptLimits()

    def _connector(self) -> Callable[..., Any]:
        if self._connect is not None:
            return self._connect
        from websockets.asyncio.client import connect

        return connect

    async def run(
        self,
        *,
        script_id: str,
        agent: str,
        source: str,
        stub: str,
        limits: ScriptLimits,
        dispatch: Callable[[ScriptRequest], Awaitable[DispatchReply]],
        procedure_id: str | None = None,
    ) -> ScriptOutcome:
        tools: list[str] = []
        outcome = await self._run(script_id, source, stub, limits, dispatch, tools)
        if self._learning is not None:
            task = asyncio.create_task(
                self._learn(script_id, agent, source, outcome, tools, procedure_id)
            )
            task.add_done_callback(lambda t: t.exception())
        return outcome

    async def _learn(
        self,
        script_id: str,
        agent: str,
        source: str,
        outcome: ScriptOutcome,
        tools: list[str],
        procedure_id: str | None,
    ) -> None:
        try:
            await self._learning.record(
                script_id=script_id,
                agent=agent,
                source=source,
                outcome=outcome,
                tools=tools,
                procedure_id=procedure_id,
            )
        except Exception as exc:
            log.warning("script_learning_failed", error=str(exc))

    async def _run(
        self,
        script_id: str,
        source: str,
        stub: str,
        limits: ScriptLimits,
        dispatch: Callable[[ScriptRequest], Awaitable[DispatchReply]],
        tools: list[str],
    ) -> ScriptOutcome:
        try:
            stat = await self._client.stat()
        except WorkspaceUnavailableError as exc:
            return _unavailable(str(exc))
        if not stat.scripts_isolated:
            return _unavailable("scripts are not isolated on this workspace computer")

        deadline = limits.wall_seconds + self._grace
        try:
            async with self._connector()(
                self._client.scripts_url(),
                additional_headers=self._client.scripts_headers(),
                max_size=WS_MAX_SIZE,
            ) as ws:
                try:
                    return await asyncio.wait_for(
                        self._converse(
                            ws, script_id, source, stub, limits, dispatch, tools
                        ),
                        timeout=deadline,
                    )
                except asyncio.TimeoutError:
                    await self._cancel(ws)
                    return ScriptOutcome(status="timeout")
        except OSError as exc:
            return _unavailable(str(exc))
        except Exception as exc:
            log.warning("script_connection_failed", error=str(exc))
            return _unavailable(str(exc))

    async def _cancel(self, ws: Any) -> None:
        try:
            await ws.send(json.dumps({"type": "cancel"}))
        except Exception:
            pass

    async def _converse(
        self,
        ws: Any,
        script_id: str,
        source: str,
        stub: str,
        limits: ScriptLimits,
        dispatch: Callable[[ScriptRequest], Awaitable[DispatchReply]],
        tools: list[str],
    ) -> ScriptOutcome:
        await ws.send(
            json.dumps(
                {
                    "type": "start",
                    "id": script_id,
                    "source": source,
                    "stub": stub,
                    "timeout_seconds": limits.wall_seconds,
                }
            )
        )
        while True:
            frame = json.loads(await ws.recv())
            kind = frame.get("type")
            if kind == "end":
                status = frame.get("status")
                return ScriptOutcome(
                    status=status if status in _END_STATUSES else "unavailable",
                    value=frame.get("value"),
                    writes=list(frame.get("writes") or []),
                    stderr_tail=frame.get("stderr_tail") or "",
                    exception=frame.get("exception"),
                )
            if kind != "call":
                continue
            request = ScriptRequest(
                seq=int(frame["seq"]),
                tool=str(frame["tool"]),
                args=dict(frame.get("args") or {}),
            )
            tools.append(request.tool)
            try:
                reply = await dispatch(request)
            except Exception as exc:
                log.warning("script_dispatch_failed", tool=request.tool, error=str(exc))
                reply = DispatchReply(ok=False, error=f"{type(exc).__name__}: {exc}")
            body: dict[str, Any] = {"type": "reply", "seq": request.seq, "ok": reply.ok}
            if reply.ok:
                body["value"] = reply.value
            else:
                body["error"] = reply.error or "error"
            await ws.send(json.dumps(body))
            if reply.stop:
                await self._cancel(ws)
