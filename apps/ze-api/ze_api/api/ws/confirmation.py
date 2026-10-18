from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from ze_agents.tasks import fire_and_forget
from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.context import bound_turn_context
from ze_api.api.ws.rollback_state import (
    deliver_retry_reply,
    move_rollback,
    retry_replaces_of,
)
from ze_api.wiring.push_kinds import CONFIRMATION_REQUEST
from ze_api.api.ws.serializers import extract_thread_id
from ze_api.api.ws.session_titles import schedule_session_title_from_thread
from ze_logging import get_logger
from ze_api.api.ws.frames import build_confirm_frame, confirmation_payload
from ze_core.conversation.turn import NO_PENDING_CONFIRMATION, turn_has_reply
from ze_api.api.ws.held import handle_held_confirm

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

    if await handle_held_confirm(data, container, conn_mgr, thread_id):
        return None

    row: dict | None = None
    if confirmation_store is not None:
        row = await confirmation_store.get_pending(request_id)
        if row is None:
            await _no_pending(conn_mgr, thread_id, request_id)
            return None
        thread_id = row.get("thread_id") or thread_id
        if pending_config is None or extract_thread_id(pending_config) != thread_id:
            pending_config = container._build_config(thread_id, **_retry_identity(row))
    elif pending_config is None:
        await _no_pending(conn_mgr, thread_id, request_id)
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

    # A paused retry: its resolution supersedes the retried reply (Phase 180).
    old_id = retry_replaces_of(pending_config)

    if not conn_mgr.try_set_busy(thread_id):
        await conn_mgr.send_frame({"type": "error", "detail": "busy"}, thread_id)
        return request_id, pending_config
    try:
        # Whoever clears the row answers it: a second answer (or the timeout) loses.
        if confirmation_store is not None and thread_id:
            if not await confirmation_store.clear(thread_id, request_id):
                await _no_pending(conn_mgr, thread_id)
                return None
            # Every client (other tabs, other devices) closes the answered card.
            await conn_mgr.send_frame(
                {"type": "confirm_cancel", "id": request_id, "reason": "answered"},
                thread_id,
            )
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
        await _retry_without_reply(container, msg_store, conn_mgr, thread_id, old_id)
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
        old_id=old_id,
    )


async def _no_pending(
    conn_mgr: ConnectionManager, thread_id: str, request_id: str = ""
) -> None:
    if request_id:
        # A screen button's gate is lost on restart; its card needs an answer too.
        await conn_mgr.send_frame(
            {
                "type": "ui_action_result",
                "id": request_id,
                "ok": False,
                "line": "That request expired.",
                "code": None,
            },
            thread_id,
        )
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
    old_id: UUID | None = None,
) -> tuple[str, dict] | None:
    """Send the reply of a resumed turn, or open the next confirmation.

    `old_id` is the reply a paused retry replaces: the resumed reply supersedes it,
    and a resume with no reply leaves it (the undo stands).
    """
    if turn_has_reply(outcome):
        if session_store is not None and thread_id:
            preview = outcome.response[:120].strip() if outcome.response else None
            try:
                await session_store.upsert(thread_id, preview=preview)
            except Exception as exc:
                log.warning("ws_session_preview_update_failed", error=str(exc))

            if msg_store is not None and outcome.response:
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
    if not turn_has_reply(outcome):
        await _retry_without_reply(container, msg_store, conn_mgr, thread_id, old_id)
    return None


CHAT_THREAD_TARGET = "chat_thread"


async def notify_confirmation_request(
    notifier: Any, prompt: str, thread_id: str | None = None
) -> None:
    """Ring the bell for an open card; the row opens the thread the card is on."""
    try:
        await notifier.notify(
            CONFIRMATION_REQUEST,
            "Ze needs your approval",
            prompt or "Ze needs your approval.",
            target_type=CHAT_THREAD_TARGET if thread_id else None,
            target_id=thread_id or None,
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
    old_id = retry_replaces_of(graph_config)
    try:
        with bound_turn_context(thread_id):
            outcome = await container.resume_turn(
                graph_config, resume={"choice": "timeout"}, request_id=request_id
            )
    except Exception as exc:
        log.exception("ws_timeout_resume_error", error=str(exc))
        await _retry_without_reply(container, None, conn_mgr, thread_id, old_id)
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
        old_id=old_id,
    )


async def supersede_open_confirmations(
    conn_mgr: ConnectionManager,
    confirmation_store: Any,
    thread_id: str,
    *,
    msg_store: Any | None = None,
) -> list[dict]:
    """Clear and cancel every open confirmation on the thread; returns the cleared rows.

    A newer turn's checkpoint replaced theirs, so they can no longer be answered.
    A paused retry among them ends with no reply: its undo stands (Phase 180).
    """
    stale = await confirmation_store.get_pending_for_thread(thread_id)
    cleared = []
    for row in stale:
        if await confirmation_store.clear(thread_id, row["request_id"]):
            cleared.append(row)
            old_id = retry_replaces_of({"configurable": _retry_identity(row)})
            await _retry_without_reply(None, msg_store, conn_mgr, thread_id, old_id)
        await conn_mgr.send_frame(
            {"type": "confirm_cancel", "id": row["request_id"]}, thread_id
        )
    return cleared


def _retry_identity(row: dict) -> dict[str, Any]:
    """The retry keys a pending row carries, as graph config extras (Phase 180)."""
    payload = row.get("actions")
    replaces = payload.get("retry_replaces") if isinstance(payload, dict) else None
    if not replaces:
        return {}
    return {"retry_mode": True, "retry_replaces": str(replaces)}


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
            conn_mgr,
            confirmation_store,
            effective_thread_id,
            msg_store=getattr(container, "message_store", None),
        )
        replaces = retry_replaces_of(outcome.config)
        await confirmation_store.save(
            thread_id=effective_thread_id,
            request_id=request_id,
            prompt=frame["title"],
            actions=confirmation_payload(
                confirmation, str(replaces) if replaces else None
            ),
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
            notify_confirmation_request(notifier, body, effective_thread_id),
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
