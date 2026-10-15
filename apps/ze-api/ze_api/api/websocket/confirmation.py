from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket

from ze_agents.tasks import fire_and_forget
from ze_api.api.websocket.connection import ConnectionManager
from ze_api.api.websocket.context import bound_turn_context
from ze_api.api.websocket.rollback_state import (
    deliver_retry_reply,
    move_rollback,
    retry_replaces_of,
)
from ze_api.push_kinds import CONFIRMATION_REQUEST, CONFIRMATION_TIMEOUT
from ze_api.api.websocket.serializers import (
    ephemeral_assistant_message,
    extract_thread_id,
)
from ze_api.api.websocket.session_titles import schedule_session_title_from_thread
from ze_logging import get_logger
from ze_workspace import rest as workspace_rest
from ze_core.orchestration.promote import confirmation_timeout_message

log = get_logger(__name__)


def _without_retry_identity(outcome: Any) -> None:
    """The reply was delivered and superseded the original: a later gate in the same
    turn must not supersede again. `retry_mode` stays, so the rest of the turn still
    refuses irreversible writes."""
    configurable = (getattr(outcome, "config", None) or {}).get("configurable")
    if isinstance(configurable, dict):
        outcome.config = {
            **outcome.config,
            "configurable": {
                k: v for k, v in configurable.items() if k != "retry_replaces"
            },
        }


async def _retry_without_reply(
    container: Any,
    msg_store: Any | None,
    conn_mgr: ConnectionManager,
    thread_id: str,
    old_id: UUID | None,
) -> None:
    """A paused retry ended with no reply: the undo stands, the old reply stays."""
    if old_id is None:
        return
    store = msg_store or getattr(container, "message_store", None)
    if store is None:
        return
    try:
        await move_rollback(
            store, conn_mgr, thread_id, old_id, "rolled_back_retry_failed"
        )
    except Exception as exc:
        log.warning("ws_retry_rollback_state_failed", error=str(exc))


async def _deliver_resumed_reply(
    container: Any,
    msg_store: Any | None,
    conn_mgr: ConnectionManager,
    thread_id: str,
    outcome: Any,
    old_id: UUID | None,
    *,
    with_trace: bool,
) -> None:
    """Send the reply a resumed turn produced; a paused retry's reply supersedes."""
    components = outcome.final_state.get("components", [])
    trace = outcome.final_state.get("message_trace") if with_trace else None
    store = msg_store or getattr(container, "message_store", None)
    if old_id is not None and store is not None:
        message = await store.get_message(old_id)
        delivered = await deliver_retry_reply(
            container,
            store,
            conn_mgr,
            thread_id=thread_id,
            old_id=old_id,
            outcome=outcome,
            record=message.rollback if message is not None else None,
            components=components or None,
        )
        if not delivered:
            await conn_mgr.send_frame(
                {"type": "error", "detail": "Resume failed."}, thread_id
            )
        return
    await container.interface.send_with_thread(
        outcome.response,
        thread_id=thread_id,
        components=components or None,
        trace=trace,
    )


async def handle_confirm(
    ws: WebSocket,
    data: dict,
    container: Any,
    conn_mgr: ConnectionManager,
    pending_config: dict | None,
    *,
    thread_id: str,
    confirmation_store: Any | None = None,
    session_store: Any | None = None,
    msg_store: Any | None = None,
) -> tuple[str, dict] | None:
    choice = data.get("choice", "")
    request_id = data.get("id", "")

    if workspace_rest.has_pending_reset(request_id):
        if confirmation_store is not None and thread_id:
            await confirmation_store.clear(thread_id, request_id)
        if choice == "approve":
            try:
                await workspace_rest.execute_reset(
                    container.workspace_store, container.workspace_client
                )
            except Exception as exc:
                log.exception("workspace_reset_failed", error=str(exc))
                await conn_mgr.send_frame(
                    {"type": "error", "detail": "Workspace reset failed."}, thread_id
                )
                return None
            workspace_rest.drop_pending_reset(request_id)
        else:
            workspace_rest.drop_pending_reset(request_id)
        await conn_mgr.send_frame(
            {"type": "confirm_cancel", "id": request_id}, thread_id
        )
        return None

    if pending_config is None:
        await conn_mgr.send_frame(
            {"type": "error", "detail": "No pending confirmation."}, thread_id
        )
        return None

    if confirmation_store is not None and thread_id:
        await confirmation_store.clear(thread_id, request_id)

    old_id = retry_replaces_of(pending_config)

    if choice == "approve":
        if not conn_mgr.try_set_busy(thread_id):
            await conn_mgr.send_frame({"type": "error", "detail": "busy"}, thread_id)
            return request_id, pending_config
        try:
            await conn_mgr.send_frame({"type": "typing"}, thread_id)
            with bound_turn_context(thread_id):
                outcome = await container.resume_turn(
                    pending_config,
                    resume={
                        "choice": "approve",
                        "edited_content": data.get("edited_content"),
                    },
                )
        except Exception as exc:
            log.exception("ws_resume_error", error=str(exc))
            await conn_mgr.send_frame(
                {"type": "error", "detail": "Resume failed."}, thread_id
            )
            await _retry_without_reply(
                container, msg_store, conn_mgr, thread_id, old_id
            )
            return None
        finally:
            conn_mgr.clear_busy(thread_id)

        if outcome.response:
            if session_store is not None and thread_id:
                preview = outcome.response[:120].strip()
                try:
                    await session_store.upsert(thread_id, preview=preview)
                except Exception as exc:
                    log.warning("ws_session_preview_update_failed", error=str(exc))

                if msg_store is not None:
                    await schedule_session_title_from_thread(
                        container,
                        session_store,
                        msg_store,
                        thread_id,
                        outcome.response,
                    )

            await _deliver_resumed_reply(
                container,
                msg_store,
                conn_mgr,
                thread_id,
                outcome,
                old_id,
                with_trace=True,
            )
            if old_id is not None:
                _without_retry_identity(outcome)
        if outcome.interrupted:
            return await send_confirmation_request(
                conn_mgr,
                container,
                outcome,
                thread_id,
                confirmation_store=confirmation_store,
            )
        if not outcome.response:
            await _retry_without_reply(
                container, msg_store, conn_mgr, thread_id, old_id
            )
        return None

    try:
        graph_state = await container.graph.aget_state(pending_config)
        in_node = bool(getattr(graph_state, "interrupts", None))
    except Exception:
        in_node = False
    if in_node:
        if not conn_mgr.try_set_busy(thread_id):
            await conn_mgr.send_frame({"type": "error", "detail": "busy"}, thread_id)
            return request_id, pending_config
        try:
            with bound_turn_context(thread_id):
                outcome = await container.resume_turn(
                    pending_config, resume={"choice": "deny"}
                )
        except Exception as exc:
            log.exception("ws_resume_deny_error", error=str(exc))
            await conn_mgr.send_frame(
                {"type": "error", "detail": "Resume failed."}, thread_id
            )
            await _retry_without_reply(
                container, msg_store, conn_mgr, thread_id, old_id
            )
            return None
        finally:
            conn_mgr.clear_busy(thread_id)
        if outcome.response:
            await _deliver_resumed_reply(
                container,
                msg_store,
                conn_mgr,
                thread_id,
                outcome,
                old_id,
                with_trace=False,
            )
            if old_id is not None:
                _without_retry_identity(outcome)
        if outcome.interrupted:
            return await send_confirmation_request(
                conn_mgr,
                container,
                outcome,
                thread_id,
                confirmation_store=confirmation_store,
            )
        if not outcome.response:
            await _retry_without_reply(
                container, msg_store, conn_mgr, thread_id, old_id
            )
        return None

    try:
        await container.abort_pending_checkpoint(pending_config)
    except Exception as exc:
        log.warning("ws_deny_abort_failed", error=str(exc))
    await conn_mgr.send_frame({"type": "confirm_cancel", "id": request_id}, thread_id)
    await _retry_without_reply(container, msg_store, conn_mgr, thread_id, old_id)
    return None


async def notify_confirmation_request(notifier: Any, prompt: str) -> None:
    try:
        await notifier.notify(
            CONFIRMATION_REQUEST,
            "Ze needs your approval",
            prompt or "Ze needs your approval.",
        )
    except Exception as exc:
        log.warning("ws_confirmation_notify_failed", error=str(exc))


async def confirmation_timeout(
    confirmation_store: Any,
    conn_mgr: ConnectionManager,
    notifier: Any | None,
    thread_id: str,
    timeout_seconds: int,
    request_id: str = "",
    container: Any | None = None,
    graph_config: dict | None = None,
) -> None:
    await asyncio.sleep(timeout_seconds)
    cleared = await confirmation_store.clear(thread_id, request_id)
    if not cleared:
        return

    log.info("confirmation_timeout_elapsed", thread_id=thread_id)

    if container is not None and graph_config is not None:
        try:
            await container.abort_pending_checkpoint(graph_config)
        except Exception as exc:
            log.warning("ws_timeout_checkpoint_abort_failed", error=str(exc))

    await _retry_without_reply(
        container, None, conn_mgr, thread_id, retry_replaces_of(graph_config)
    )

    timeout_msg = confirmation_timeout_message(
        await _conductor_ledger_from_graph(container, graph_config)
    )
    await conn_mgr.send_frame(
        {
            "type": "message",
            "message": ephemeral_assistant_message(timeout_msg),
        },
        thread_id,
    )
    if notifier is not None:
        try:
            await notifier.notify(
                CONFIRMATION_TIMEOUT,
                "Approval request expired",
                timeout_msg,
                target_type="thread",
                target_id=thread_id,
            )
        except Exception as exc:
            log.warning("ws_timeout_ntfy_failed", error=str(exc))


async def send_confirmation_request(
    conn_mgr: ConnectionManager,
    container: Any,
    outcome: Any,
    thread_id: str,
    *,
    confirmation_store: Any | None = None,
) -> tuple[str, dict]:
    """Persist, notify, and frame a confirmation request; returns (request_id, graph config)."""
    request_id = str(getattr(outcome, "confirm_request_id", "") or "") or str(uuid4())
    effective_thread_id = extract_thread_id(outcome.config) or thread_id or ""
    confirm_timeout = getattr(container.settings, "confirm_timeout_seconds", 900)

    frame = {
        "type": "confirm_request",
        "id": request_id,
        "prompt": outcome.draft or "",
        "editable": bool(getattr(outcome, "confirm_editable", False)),
        "proposed": getattr(outcome, "confirm_proposed", "") or "",
        "actions": [
            {"label": "Approve", "value": "approve", "style": "primary"},
            {"label": "Cancel", "value": "deny", "style": "secondary"},
        ],
    }

    if confirmation_store is not None and effective_thread_id:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=confirm_timeout)
        await confirmation_store.save(
            thread_id=effective_thread_id,
            request_id=request_id,
            prompt=outcome.draft or "",
            actions=frame["actions"],
            expires_at=expires_at,
        )

    await conn_mgr.send_frame(frame, effective_thread_id or None)

    notifier = getattr(container, "notifier", None)
    if notifier is not None:
        fire_and_forget(
            notify_confirmation_request(notifier, outcome.draft or ""),
            label="notify_confirmation_request",
        )

    if confirmation_store is not None and effective_thread_id:
        asyncio.create_task(
            confirmation_timeout(
                confirmation_store,
                conn_mgr,
                notifier,
                effective_thread_id,
                confirm_timeout,
                request_id,
                container=container,
                graph_config=outcome.config,
            )
        )

    return request_id, outcome.config


async def _conductor_ledger_from_graph(
    container: Any | None, graph_config: dict | None
) -> list:
    if container is None or graph_config is None:
        return []
    graph = getattr(container, "graph", None)
    aget_state = getattr(graph, "aget_state", None) if graph is not None else None
    if aget_state is None:
        return []
    try:
        snapshot = await aget_state(graph_config)
    except Exception as exc:
        log.warning("ws_timeout_ledger_lookup_failed", error=str(exc))
        return []
    values = getattr(snapshot, "values", None)
    if not isinstance(values, dict):
        return []
    ledger = values.get("conductor_ledger")
    return list(ledger) if isinstance(ledger, list) else []
