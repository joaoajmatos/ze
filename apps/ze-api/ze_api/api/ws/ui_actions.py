"""Tool actions pressed on a screen (Phase 191a, contracts/primitive-actions.md).

A `ui_action` frame names one of an agent's opted-in WRITE tools. A reversible tool
runs at once; an asks-first tool opens an in-process gate that asks through the
normal `confirm_request` card. Every run writes one `ui.tool_action` ActionRecord.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from ze_agents.effects import effect_imperative
from ze_agents.errors import UiActionRefusedError
from ze_agents.park import ApprovedCall, ConfirmItem
from ze_agents.registry import get_enabled_instances
from ze_agents.rollback import is_error_result
from ze_agents.tool import ToolAccess, get_tool
from ze_agents.types import AgentContext, ToolCall
from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.ui_gates import UiActionGate
from ze_api.api.ws.context import bound_turn_context
from ze_api.api.ws.frames import build_confirm_frame
from ze_api.api.ws.schemas import WsUiActionFrame
from ze_logging import get_logger
from ze_memory.action_records.recorder import ActionRecorder, safe_record_action
from ze_memory.action_records.types import (
    ActionContext,
    ActionLifecycle,
    ActionOutcome,
)

log = get_logger(__name__)

UNAVAILABLE = "That action is not available."
EXPIRED = "That request expired."
BUSY = "Ze is busy with another request. Try again in a moment."
DEFAULT_DONE = "Done."


def _declined(effect: str) -> str:
    return f"Okay, I didn't {effect}."


def _result_frame(
    request_id: str, thread_id: str, *, ok: bool, line: str, code: str | None = None
) -> dict[str, Any]:
    return {
        "type": "ui_action_result",
        "id": request_id,
        "thread_id": thread_id,
        "ok": ok,
        "line": line,
        "code": code,
    }


async def _send_result(
    conn_mgr: ConnectionManager,
    request_id: str,
    thread_id: str,
    *,
    ok: bool,
    line: str,
    code: str | None = None,
) -> None:
    await conn_mgr.send_frame(
        _result_frame(request_id, thread_id, ok=ok, line=line, code=code), thread_id
    )


def _plugin_of(agent: Any) -> str:
    return type(agent).__module__.split(".")[0].replace("_", "-")


def _args_hash(args: dict[str, Any]) -> str:
    raw = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _uuid_or_none(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


async def _record(
    container: Any,
    *,
    request_id: str,
    agent: str,
    plugin: str,
    tool: str,
    args: dict[str, Any],
    effect: str,
    lifecycle: ActionLifecycle,
    outcome: ActionOutcome,
    failure_code: str | None = None,
) -> None:
    """One `ui.tool_action` record per UI request. A ledger failure never fails the action."""
    store = getattr(container, "action_record_store", None)
    recorder = ActionRecorder(store) if store is not None else None
    await safe_record_action(
        recorder,
        producer_kind="ui",
        source_record_type="request",
        source_record_id=request_id,
        action_kind="tool_action",
        lifecycle=lifecycle,
        outcome=outcome,
        actor="user",
        producer_plugin=plugin,
        occurred_at=datetime.now(timezone.utc),
        summary=(
            f"{agent}.{tool} ({effect}) {lifecycle.value}; args {_args_hash(args)}"
        ),
        context=ActionContext(request_id=_uuid_or_none(request_id)),
        failure_code=failure_code,
    )
    log.info(
        "ui_action_run",
        request_id=request_id,
        owner=agent,
        tool=tool,
        lifecycle=lifecycle.value,
    )


def _resolve(owner: str, tool: str) -> tuple[Any, Any]:
    """The owner's live agent and the opted-in WRITE tool it names, or a refusal."""
    agent = get_enabled_instances().get(owner)
    if agent is None or tool not in (getattr(agent, "tools", None) or []):
        raise UiActionRefusedError(f"{owner!r} has no tool {tool!r}")
    try:
        spec = get_tool(tool)
    except Exception:
        raise UiActionRefusedError(f"unknown tool {tool!r}") from None
    if spec.access is not ToolAccess.WRITE or not spec.ui_action:
        raise UiActionRefusedError(f"tool {tool!r} is not a screen action")
    return agent, spec


def _context(thread_id: str) -> AgentContext:
    return AgentContext(session_id=thread_id, prompt="")


async def handle_ui_action(
    data: dict, container: Any, conn_mgr: ConnectionManager
) -> None:
    request_id = str(data.get("id") or "")
    thread_id = str(data.get("thread_id") or "")
    try:
        frame = WsUiActionFrame.model_validate(data)
    except ValidationError:
        if request_id and thread_id:
            await _send_result(
                conn_mgr, request_id, thread_id, ok=False, line=UNAVAILABLE
            )
        return
    action = frame.action
    try:
        agent, spec = _resolve(action.owner, action.tool)
    except UiActionRefusedError as exc:
        log.info("ui_action_refused", request_id=request_id, reason=str(exc))
        await _send_result(conn_mgr, request_id, thread_id, ok=False, line=UNAVAILABLE)
        return
    effect = effect_imperative(spec.effect_phrase or spec.name)
    plugin = _plugin_of(agent)
    args = dict(action.args)

    if not conn_mgr.try_set_busy(thread_id):
        await _send_result(
            conn_mgr, request_id, thread_id, ok=False, line=BUSY, code="busy"
        )
        return
    try:
        with bound_turn_context(thread_id):
            try:
                tc = await agent.run_action(action.tool, args, _context(thread_id))
            except UiActionRefusedError as exc:
                log.info("ui_action_refused", request_id=request_id, reason=str(exc))
                await _send_result(
                    conn_mgr, request_id, thread_id, ok=False, line=UNAVAILABLE
                )
                return
            except Exception as exc:
                log.warning("ui_action_error", request_id=request_id, error=str(exc))
                tc = None
        if tc is not None and tc.gate == "parked" and tc.parked is not None:
            await _open_gate(
                container, conn_mgr, request_id, thread_id, agent, plugin, tc, effect
            )
            return
        await _finish(
            container,
            conn_mgr,
            request_id,
            thread_id,
            agent.name,
            plugin,
            spec,
            args,
            effect,
            tc,
        )
    finally:
        conn_mgr.clear_busy(thread_id)


async def _finish(
    container: Any,
    conn_mgr: ConnectionManager,
    request_id: str,
    thread_id: str,
    owner: str,
    plugin: str,
    spec: Any,
    args: dict[str, Any],
    effect: str,
    tc: ToolCall | None,
) -> None:
    ok = tc is not None and tc.success and not is_error_result(tc.result)
    await _record(
        container,
        request_id=request_id,
        agent=owner,
        plugin=plugin,
        tool=spec.name,
        args=args,
        effect=effect,
        lifecycle=ActionLifecycle.SUCCEEDED if ok else ActionLifecycle.FAILED,
        outcome=ActionOutcome.SUCCESS if ok else ActionOutcome.FAILURE,
        failure_code=None if ok else ("error" if tc is None else (tc.gate or "error")),
    )
    line = (spec.done_phrase or DEFAULT_DONE) if ok else f"Couldn't {effect}."
    await _send_result(conn_mgr, request_id, thread_id, ok=ok, line=line)


async def _open_gate(
    container: Any,
    conn_mgr: ConnectionManager,
    request_id: str,
    thread_id: str,
    agent: Any,
    plugin: str,
    tc: ToolCall,
    effect: str,
) -> None:
    parked = tc.parked
    timeout = getattr(container.settings, "confirm_timeout_seconds", 900)
    item = ConfirmItem(
        item_id=parked.item_id,
        agent=parked.agent,
        tool=parked.tool,
        effect_phrase=parked.effect_phrase,
        summary=parked.summary,
        editable_field=None,
        conflict=parked.conflict,
    )
    frame = build_confirm_frame(
        request_id=request_id,
        thread_id=thread_id,
        kind="write",
        round_=1,
        items=[asdict(item)],
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=timeout),
    )
    gate = UiActionGate(
        request_id=request_id,
        thread_id=thread_id,
        agent=agent.name,
        plugin=plugin,
        tool=parked.tool,
        args=dict(parked.args),
        parked=parked,
        effect=effect,
        frame=frame,
    )
    gates = conn_mgr.ui_gates
    gates.add(gate)
    gate.timer = asyncio.create_task(_expire(container, conn_mgr, gate, timeout))
    await conn_mgr.send_frame(frame, thread_id)


async def _expire(
    container: Any, conn_mgr: ConnectionManager, gate: UiActionGate, timeout: float
) -> None:
    await conn_mgr.ui_gates.sleep(timeout)
    if conn_mgr.ui_gates.pop(gate.request_id) is None:
        return
    await _close_declined(
        container,
        conn_mgr,
        gate,
        ActionLifecycle.TIMED_OUT,
        ActionOutcome.TIMEOUT,
        cancel_timer=False,
    )


async def _close_declined(
    container: Any,
    conn_mgr: ConnectionManager,
    gate: UiActionGate,
    lifecycle: ActionLifecycle,
    outcome: ActionOutcome,
    *,
    cancel_timer: bool = True,
    reason: str | None = None,
) -> None:
    if cancel_timer and gate.timer is not None:
        gate.timer.cancel()
    cancel = {"type": "confirm_cancel", "id": gate.request_id}
    if reason:
        cancel["reason"] = reason
    await conn_mgr.send_frame(cancel, gate.thread_id)
    await _record(
        container,
        request_id=gate.request_id,
        agent=gate.agent,
        plugin=gate.plugin,
        tool=gate.tool,
        args=gate.args,
        effect=gate.effect,
        lifecycle=lifecycle,
        outcome=outcome,
        failure_code="confirm_timeout"
        if lifecycle is ActionLifecycle.TIMED_OUT
        else None,
    )
    await _send_result(
        conn_mgr, gate.request_id, gate.thread_id, ok=False, line=_declined(gate.effect)
    )


async def handle_ui_confirm(
    data: dict, container: Any, conn_mgr: ConnectionManager
) -> bool:
    """Answer a UI gate. False when `data["id"]` was never a UI gate (graph path)."""
    request_id = str(data.get("id") or "")
    gates = conn_mgr.ui_gates
    gate = gates.pop(request_id)
    thread_id = str(data.get("thread_id") or "")
    if gate is None:
        if gates.was_closed(request_id):
            await _send_result(conn_mgr, request_id, thread_id, ok=False, line=EXPIRED)
            return True
        return False
    thread_id = gate.thread_id
    choice = data.get("choice", "")
    if choice != "approve":
        await _close_declined(
            container,
            conn_mgr,
            gate,
            ActionLifecycle.CANCELLED,
            ActionOutcome.CANCELLED,
            reason="answered",
        )
        return True

    agent = get_enabled_instances().get(gate.agent)
    if agent is None or not conn_mgr.try_set_busy(thread_id):
        gates.add(gate)
        await _send_result(
            conn_mgr, request_id, thread_id, ok=False, line=BUSY, code="busy"
        )
        return True
    if gate.timer is not None:
        gate.timer.cancel()
    try:
        await conn_mgr.send_frame(
            {"type": "confirm_cancel", "id": request_id, "reason": "answered"},
            thread_id,
        )
        try:
            with bound_turn_context(thread_id):
                tc = await agent.run_action(
                    gate.tool,
                    gate.args,
                    _context(thread_id),
                    approval=ApprovedCall(gate.parked.call_id),
                    approval_request_id=request_id,
                )
        except Exception as exc:
            log.warning("ui_action_error", request_id=request_id, error=str(exc))
            tc = None
        spec = get_tool(gate.tool)
        await _finish(
            container,
            conn_mgr,
            request_id,
            thread_id,
            gate.agent,
            gate.plugin,
            spec,
            gate.args,
            gate.effect,
            tc,
        )
    finally:
        conn_mgr.clear_busy(thread_id)
    return True


async def supersede_ui_gates(
    container: Any, conn_mgr: ConnectionManager, thread_id: str
) -> None:
    """A new turn on the thread ends its open UI gates: nothing ran."""
    gates = conn_mgr.ui_gates
    for gate in gates.for_thread(thread_id):
        if gates.pop(gate.request_id) is None:
            continue
        await _close_declined(
            container,
            conn_mgr,
            gate,
            ActionLifecycle.CANCELLED,
            ActionOutcome.CANCELLED,
        )
