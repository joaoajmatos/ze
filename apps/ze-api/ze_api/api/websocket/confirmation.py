from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import WebSocket

from ze_agents.tasks import fire_and_forget
from ze_api.api.websocket.connection import ConnectionManager
from ze_api.api.websocket.context import bound_turn_context
from ze_api.push_kinds import CONFIRMATION_REQUEST
from ze_api.api.websocket.serializers import extract_thread_id
from ze_api.api.websocket.session_titles import schedule_session_title_from_thread
from ze_logging import get_logger
from ze_workspace import rest as workspace_rest
from ze_api.api.websocket.frames import build_confirm_frame, confirmation_payload
from ze_core.conversation.turn import NO_PENDING_CONFIRMATION
from ze_api.api.websocket.held import handle_held_confirm

log = get_logger(__name__)


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

    if await handle_held_confirm(data, container, conn_mgr, thread_id):
        return None

    row: dict | None = None
    if confirmation_store is not None:
        row = await confirmation_store.get_pending(request_id)
        if row is None:
            await _no_pending(conn_mgr, thread_id)
            return None
        thread_id = row.get("thread_id") or thread_id
        if pending_config is None or extract_thread_id(pending_config) != thread_id:
            pending_config = container._build_config(thread_id)
    elif pending_config is None:
        await _no_pending(conn_mgr, thread_id)
        return None

    if choice not in ("approve", "deny"):
        await conn_mgr.send_frame(
            {"type": "error", "detail": "invalid choice"}, thread_id
        )
        return request_id, pending_config

    edits = data.get("edits") or {}
    if not _valid_edits(edits, row):
        await conn_mgr.send_frame(
            {"type": "error", "detail": "invalid edit"}, thread_id
        )
        return request_id, pending_config

    if not conn_mgr.try_set_busy(thread_id):
        await conn_mgr.send_frame({"type": "error", "detail": "busy"}, thread_id)
        return request_id, pending_config
    try:
        # Whoever clears the row answers it: a second answer (or the timeout) loses.
        if confirmation_store is not None and thread_id:
            if not await confirmation_store.clear(thread_id, request_id):
                await _no_pending(conn_mgr, thread_id)
                return None
        await conn_mgr.send_frame({"type": "typing"}, thread_id)
        with bound_turn_context(thread_id):
            outcome = await container.resume_turn(
                pending_config,
                resume={"choice": choice, "edits": edits},
                request_id=request_id,
            )
    except Exception as exc:
        log.exception("ws_resume_error", error=str(exc))
        await conn_mgr.send_frame(
            {"type": "error", "detail": "Resume failed."}, thread_id
        )
        return None
    finally:
        conn_mgr.clear_busy(thread_id)

    if outcome.error == NO_PENDING_CONFIRMATION:
        await _no_pending(conn_mgr, thread_id)
        return None
    return await _deliver_outcome(
        outcome,
        container,
        conn_mgr,
        thread_id,
        confirmation_store=confirmation_store,
        session_store=session_store,
        msg_store=msg_store,
    )


async def _no_pending(conn_mgr: ConnectionManager, thread_id: str) -> None:
    await conn_mgr.send_frame(
        {"type": "error", "detail": "No pending confirmation."}, thread_id
    )


def _valid_edits(edits: Any, row: dict | None) -> bool:
    if not edits:
        return True
    if not isinstance(edits, dict) or row is None:
        return False
    payload = row.get("actions")
    items = payload.get("items") if isinstance(payload, dict) else None
    editable = {
        item.get("item_id") for item in items or [] if item.get("editable_field")
    }
    return all(key in editable and isinstance(val, str) for key, val in edits.items())


async def _deliver_outcome(
    outcome: Any,
    container: Any,
    conn_mgr: ConnectionManager,
    thread_id: str,
    *,
    confirmation_store: Any | None,
    session_store: Any | None = None,
    msg_store: Any | None = None,
) -> tuple[str, dict] | None:
    """Send the reply of a resumed turn, or open the next confirmation."""
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

        components = outcome.final_state.get("components", [])
        trace = outcome.final_state.get("message_trace")
        await container.interface.send_with_thread(
            outcome.response,
            thread_id=thread_id,
            components=components or None,
            trace=trace,
        )
    if outcome.interrupted:
        return await send_confirmation_request(
            conn_mgr,
            container,
            outcome,
            thread_id,
            confirmation_store=confirmation_store,
        )
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
    """After the window elapses, resume the graph as a denial: nothing runs and the
    reply says so. The reply is delivered like any other (pushed when offline)."""
    await asyncio.sleep(timeout_seconds)
    cleared = await confirmation_store.clear(thread_id, request_id)
    if not cleared:
        return

    log.info("confirmation_timeout_elapsed", thread_id=thread_id)
    await conn_mgr.send_frame({"type": "confirm_cancel", "id": request_id}, thread_id)
    if container is None or graph_config is None:
        return
    if not conn_mgr.try_set_busy(thread_id):
        # A turn is running on this thread; it supersedes the paused checkpoint.
        log.info("confirmation_timeout_thread_busy", thread_id=thread_id)
        return
    try:
        with bound_turn_context(thread_id):
            outcome = await container.resume_turn(
                graph_config, resume={"choice": "timeout"}, request_id=request_id
            )
    except Exception as exc:
        log.exception("ws_timeout_resume_error", error=str(exc))
        return
    finally:
        conn_mgr.clear_busy(thread_id)
    if outcome.error == NO_PENDING_CONFIRMATION:
        return
    await _deliver_outcome(
        outcome,
        container,
        conn_mgr,
        thread_id,
        confirmation_store=confirmation_store,
    )


async def supersede_open_confirmations(
    conn_mgr: ConnectionManager, confirmation_store: Any, thread_id: str
) -> list[dict]:
    """Clear and cancel every open confirmation on the thread; returns the cleared rows.

    A newer turn's checkpoint replaced theirs, so they can no longer be answered.
    """
    stale = await confirmation_store.get_pending_for_thread(thread_id)
    cleared = []
    for row in stale:
        if await confirmation_store.clear(thread_id, row["request_id"]):
            cleared.append(row)
        await conn_mgr.send_frame(
            {"type": "confirm_cancel", "id": row["request_id"]}, thread_id
        )
    return cleared


async def send_confirmation_request(
    conn_mgr: ConnectionManager,
    container: Any,
    outcome: Any,
    thread_id: str,
    *,
    confirmation_store: Any | None = None,
) -> tuple[str, dict]:
    """Persist, notify, and frame a confirmation request; returns (request_id, graph config)."""
    confirmation = outcome.confirmation
    request_id = confirmation.request_id
    effective_thread_id = extract_thread_id(outcome.config) or thread_id or ""
    confirm_timeout = getattr(container.settings, "confirm_timeout_seconds", 900)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=confirm_timeout)

    frame = build_confirm_frame(
        request_id=request_id,
        thread_id=effective_thread_id or None,
        kind=confirmation.kind,
        round_=confirmation.round,
        items=[asdict(item) for item in confirmation.items],
        expires_at=expires_at,
    )

    if confirmation_store is not None and effective_thread_id:
        await supersede_open_confirmations(
            conn_mgr, confirmation_store, effective_thread_id
        )
        await confirmation_store.save(
            thread_id=effective_thread_id,
            request_id=request_id,
            prompt=frame["title"],
            actions=confirmation_payload(confirmation),
            expires_at=expires_at,
        )

    await conn_mgr.send_frame(frame, effective_thread_id or None)

    notifier = getattr(container, "notifier", None)
    if notifier is not None:
        first = confirmation.items[0] if confirmation.items else None
        body = frame["title"]
        if first is not None:
            body = f"{first.effect_phrase}: {first.summary}".strip(": ")
            if len(confirmation.items) > 1:
                body += f" (+{len(confirmation.items) - 1} more)"
        fire_and_forget(
            notify_confirmation_request(notifier, body),
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
