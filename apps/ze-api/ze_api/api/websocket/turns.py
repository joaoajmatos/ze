from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket

from ze_agents.interface.types import RawInput
from ze_agents.progress.reporter import ProgressReporter
from ze_api.api.websocket.confirmation import (
    send_confirmation_request,
    supersede_open_confirmations,
)
from ze_api.api.websocket.connection import ConnectionManager
from ze_api.api.websocket.context import bound_turn_context
from ze_api.api.websocket.serializers import extract_thread_id
from ze_api.api.websocket.session_titles import schedule_session_title
from ze_agents.errors import RetryError
from ze_core.conversation.messages import Message
from ze_logging import get_logger

log = get_logger(__name__)


async def handle_message(
    ws: WebSocket,
    data: dict,
    container: Any,
    msg_store: Any,
    conn_mgr: ConnectionManager,
    pending_config: dict | None,
    *,
    confirmation_store: Any | None = None,
    session_store: Any | None = None,
) -> tuple[str, dict] | None:
    text: str = data.get("text", "")
    thread_id: str | None = data.get("thread_id") or None
    context: dict | None = data.get("context") or None

    if not text:
        return None

    if not thread_id:
        await conn_mgr.send_frame({"type": "error", "detail": "thread_id required"})
        return None

    pending_gate_id = conn_mgr.take_pending_gate_redirect(thread_id)
    if pending_gate_id is not None:
        return await _handle_gate_redirect_message(
            text,
            thread_id,
            pending_gate_id,
            container,
            msg_store,
            conn_mgr,
            session_store,
        )

    user_msg = Message(
        id=uuid4(),
        role="user",
        text=text,
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id=thread_id,
    )
    try:
        await msg_store.save(user_msg)
    except Exception as exc:
        log.warning("ws_save_user_msg_failed", error=str(exc))

    if session_store is not None and thread_id:
        title = text[:60].strip() if text else None
        try:
            await session_store.upsert(thread_id, title=title, title_source="user")
        except Exception as exc:
            log.warning("ws_session_upsert_failed", error=str(exc))

    await conn_mgr.send_frame({"type": "typing"}, thread_id)

    config_extra: dict = {}
    config_extra["user_message_id"] = str(user_msg.id)
    if context:
        config_extra["screen_context"] = context

    if getattr(container, "translations", None) is not None:

        async def _progress_sink(text: str) -> None:
            await conn_mgr.send_frame({"type": "typing", "text": text}, thread_id)

        config_extra["reporter"] = ProgressReporter(
            translations=container.translations,
            sink=_progress_sink,
        )

    async def _token_sink(chunk: str) -> None:
        await conn_mgr.send_frame({"type": "token", "text": chunk}, thread_id)

    config_extra["token_sink"] = _token_sink

    try:
        with bound_turn_context(thread_id):
            outcome = await container.invoke_raw_turn(
                thread_id,
                RawInput(text=text),
                config_extra=config_extra,
            )
    except Exception as exc:
        log.exception("ws_invoke_error", error=str(exc))
        await conn_mgr.send_frame(
            {"type": "error", "detail": "Something went wrong."}, thread_id
        )
        return None

    if outcome.interrupted:
        return await send_confirmation_request(
            conn_mgr,
            container,
            outcome,
            thread_id,
            confirmation_store=confirmation_store,
        )

    if outcome.response:
        effective_thread_id = extract_thread_id(outcome.config) or thread_id or ""
        if confirmation_store is not None and effective_thread_id:
            # This turn completed with a direct response, superseding any gate(s)
            # left open on this thread — their checkpoints can no longer be resumed.
            stale = await supersede_open_confirmations(
                conn_mgr, confirmation_store, effective_thread_id
            )
            _record_superseded(outcome.final_state.get("message_trace"), stale)

        if session_store is not None and effective_thread_id:
            preview = outcome.response[:120].strip() if outcome.response else None
            try:
                await session_store.upsert(effective_thread_id, preview=preview)
            except Exception as exc:
                log.warning("ws_session_preview_update_failed", error=str(exc))

            schedule_session_title(
                container,
                session_store,
                effective_thread_id,
                user_text=text,
                assistant_text=outcome.response,
            )

        components = outcome.final_state.get("components", [])
        trace = outcome.final_state.get("message_trace")
        await container.interface.send_with_thread(
            outcome.response,
            thread_id=extract_thread_id(outcome.config),
            components=components or None,
            trace=trace,
            message_id=outcome.message_id or None,
        )
    else:
        log.warning("ws_turn_empty_response", thread_id=thread_id)
        await conn_mgr.send_frame(
            {"type": "error", "detail": "Something went wrong."}, thread_id
        )

    return None


def _record_superseded(trace: Any, stale: list[dict]) -> None:
    """The superseding turn's trace records what the cleared confirmations asked."""
    if trace is None:
        return
    for row in stale:
        payload = row.get("actions")
        if not isinstance(payload, dict):
            continue
        for item in payload.get("items") or []:
            trace.write_confirmations.append(
                {
                    "request_id": row["request_id"],
                    "round": int(payload.get("round") or 1),
                    "item_id": item.get("item_id", ""),
                    "agent": item.get("agent", ""),
                    "tool": item.get("tool"),
                    "effect": item.get("effect_phrase"),
                    "summary": item.get("summary", ""),
                    "outcome": "superseded",
                }
            )


async def _handle_gate_redirect_message(
    text: str,
    thread_id: str,
    gate_id: UUID,
    container: Any,
    msg_store: Any,
    conn_mgr: ConnectionManager,
    session_store: Any | None,
) -> None:
    user_msg = Message(
        id=uuid4(),
        role="user",
        text=text,
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id=thread_id,
    )
    try:
        await msg_store.save(user_msg)
    except Exception as exc:
        log.warning("ws_save_user_msg_failed", error=str(exc))

    if session_store is not None:
        preview = text[:120].strip() if text else None
        try:
            await session_store.upsert(thread_id, preview=preview)
        except Exception as exc:
            log.warning("ws_session_upsert_failed", error=str(exc))

    executor = container._plugin_stores.get("goal_executor")
    if executor is None:
        await conn_mgr.send_frame(
            {"type": "error", "detail": "Goal engine unavailable"}, thread_id
        )
        return None

    await conn_mgr.send_frame({"type": "typing"}, thread_id)
    try:
        await executor.handle_gate_redirected(gate_id, text)
    except Exception as exc:
        log.exception("ws_gate_redirect_failed", error=str(exc))
        await conn_mgr.send_frame(
            {"type": "error", "detail": "Redirect failed."}, thread_id
        )
        return None

    await container.interface.send_with_thread(
        "Got it — Ze is replanning from that checkpoint.",
        thread_id=thread_id,
    )
    await conn_mgr.send_frame({"type": "refresh", "screen": "goals"}, thread_id)
    return None


async def _retry_error(
    conn_mgr: ConnectionManager,
    thread_id: str,
    message_id: str,
    code: str,
    detail: str,
    *,
    reason_code: str | None = None,
    reason_text: str | None = None,
) -> None:
    frame: dict = {
        "type": "error",
        "detail": detail,
        "code": code,
        "message_id": message_id,
    }
    if reason_code is not None:
        frame["reason_code"] = reason_code
    if reason_text is not None:
        frame["reason_text"] = reason_text
    await conn_mgr.send_frame(frame, thread_id)


async def handle_retry(
    data: dict,
    container: Any,
    msg_store: Any,
    conn_mgr: ConnectionManager,
    *,
    feedback_store: Any,
    confirmation_store: Any,
) -> None:
    """Regenerate the latest reply with writes blocked; replace it in place.

    The caller holds the per-thread busy flag. Eligibility is decided here, on the
    server, from the recorded turn; a refusal happens before any graph run.
    """
    from ze_api.feedback_views import evaluate_retry, thread_state
    from ze_memory.feedback_records import (
        FeedbackKind,
        FeedbackRecordDraft,
        feedback_contribution,
        submit_feedback_record,
    )

    thread_id: str = data.get("thread_id") or ""
    raw_id = str(data.get("message_id") or "")
    try:
        old_id = UUID(raw_id)
    except ValueError:
        await _retry_error(
            conn_mgr, thread_id, raw_id, "retry_unavailable", "Invalid message id."
        )
        return

    message = await msg_store.get_message(old_id)
    if message is None or message.role != "assistant" or message.thread_id != thread_id:
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_unavailable",
            "That reply no longer exists.",
        )
        return

    trace = await msg_store.get_trace(old_id)
    state = await thread_state(
        thread_id,
        message_store=msg_store,
        # The endpoint set this thread's busy flag for the retry itself; only a turn
        # holding the thread lock (for example a follow-up) makes it busy.
        is_busy=container.is_thread_locked,
        confirmation_store=confirmation_store,
    )
    eligibility = evaluate_retry(message, trace, state)
    if not eligibility.available:
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_unavailable",
            eligibility.reason_text or "Retry is not available.",
            reason_code=eligibility.reason_code.value
            if eligibility.reason_code
            else None,
            reason_text=eligibility.reason_text,
        )
        return

    user_msg = await msg_store.previous_user_message(old_id)
    if user_msg is None or not user_msg.text:
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_failed",
            "Ze could not find the message to answer again.",
        )
        return

    try:
        await submit_feedback_record(
            feedback_store,
            feedback_contribution(
                FeedbackRecordDraft(
                    idempotency_key=f"retry:{old_id}:{uuid4()}",
                    message_id=old_id,
                    thread_id=thread_id,
                    kind=FeedbackKind.RETRY_REQUESTED,
                    occurred_at=datetime.now(timezone.utc),
                    trace_present=trace is not None,
                )
            ),
        )
    except Exception as exc:
        log.warning("ws_retry_feedback_failed", error=str(exc))

    await conn_mgr.send_frame({"type": "typing"}, thread_id)
    config_extra: dict = {"user_message_id": str(user_msg.id)}

    async def _token_sink(chunk: str) -> None:
        await conn_mgr.send_frame({"type": "token", "text": chunk}, thread_id)

    config_extra["token_sink"] = _token_sink
    if getattr(container, "translations", None) is not None:

        async def _progress_sink(text: str) -> None:
            await conn_mgr.send_frame({"type": "typing", "text": text}, thread_id)

        config_extra["reporter"] = ProgressReporter(
            translations=container.translations, sink=_progress_sink
        )

    try:
        with bound_turn_context(thread_id):
            outcome = await container.invoke_retry_turn(
                thread_id, user_msg.text, config_extra=config_extra
            )
    except RetryError as exc:
        log.warning("ws_retry_failed", error=str(exc))
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_failed",
            "Retry failed. The original reply is unchanged.",
        )
        return
    except Exception as exc:
        log.exception("ws_retry_error", error=str(exc))
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_failed",
            "Retry failed. The original reply is unchanged.",
        )
        return

    new_id = UUID(outcome.message_id)

    async def _supersede() -> bool:
        return await msg_store.mark_superseded(old_id, new_id)

    # Store, link, then deliver: the client never sees a reply that failed to
    # replace the original.
    delivered = await container.interface.send_with_thread(
        outcome.response,
        thread_id=extract_thread_id(outcome.config) or thread_id,
        components=outcome.final_state.get("components") or None,
        trace=outcome.final_state.get("message_trace"),
        message_id=outcome.message_id,
        replaces=old_id,
        after_save=_supersede,
    )
    if not delivered:
        log.warning("ws_retry_supersede_failed", old=str(old_id), new=str(new_id))
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_failed",
            "Retry failed. The original reply is unchanged.",
        )
        return
    await conn_mgr.send_frame(
        {
            "type": "message_superseded",
            "message_id": str(old_id),
            "replaced_by": str(new_id),
        },
        thread_id,
    )
