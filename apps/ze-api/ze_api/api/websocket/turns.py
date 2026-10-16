from __future__ import annotations

from dataclasses import dataclass
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
from ze_api.api.websocket.rollback_state import (
    deliver_retry_reply,
    move_rollback,
    public_rollback_record,
    publish_rollback,
    rollback_notice,
    undone_phrases,
)
from ze_api.api.websocket.session_titles import schedule_session_title
from ze_agents.errors import RetryError
from ze_core.conversation.messages import Message
from ze_core.conversation.messages.types import RollbackRecord
from ze_core.conversation.rollback import run_rollback
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
                conn_mgr,
                confirmation_store,
                effective_thread_id,
                msg_store=getattr(container, "message_store", None),
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
    rolled_back: bool | None = None,
    rollback: RollbackRecord | None = None,
    plan: list[dict] | None = None,
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
    if rolled_back is not None:
        frame["rolled_back"] = rolled_back
    if rollback is not None:
        frame["rollback"] = public_rollback_record(rollback)
    if plan is not None:
        frame["plan"] = plan
    await conn_mgr.send_frame(frame, thread_id)


@dataclass
class _RetryPlan:
    message: Message
    trace: Any
    eligibility: Any
    old_id: UUID
    raw_id: str


async def _prepare_retry(
    data: dict,
    container: Any,
    msg_store: Any,
    conn_mgr: ConnectionManager,
    confirmation_store: Any,
    *,
    thread_held: bool,
) -> _RetryPlan | None:
    """Load the reply and decide eligibility and the plan guard; refuse before any change.

    Run once to refuse fast, and again with the thread lock held (`thread_held`), when
    nothing else can touch the thread.
    """
    from ze_api.feedback_views import evaluate_retry, public_plan, thread_state

    thread_id: str = data.get("thread_id") or ""
    raw_id = str(data.get("message_id") or "")
    try:
        old_id = UUID(raw_id)
    except ValueError:
        await _retry_error(
            conn_mgr, thread_id, raw_id, "retry_unavailable", "Invalid message id."
        )
        return None

    message = await msg_store.get_message(old_id)
    if message is None or message.role != "assistant" or message.thread_id != thread_id:
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_unavailable",
            "That reply no longer exists.",
        )
        return None

    trace = await msg_store.get_trace(old_id)
    state = await thread_state(
        thread_id,
        message_store=msg_store,
        # The endpoint set this thread's busy flag for the retry itself; only a turn
        # holding the thread lock (for example a follow-up) makes it busy. With the
        # lock held by this retry, nothing else is running.
        is_busy=(lambda _tid: False) if thread_held else container.is_thread_locked,
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
        return None

    plan = eligibility.plan
    confirmed = data.get("confirmed_plan")
    if plan and not confirmed:
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_unavailable",
            "Confirm what Retry will undo first.",
            reason_code="undo_not_confirmed",
        )
        return None
    if list(confirmed or []) != [e.entry_id for e in plan]:
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_unavailable",
            "What Retry would undo has changed. Check the list and confirm again.",
            reason_code="plan_changed",
            plan=[e.model_dump(mode="json") for e in public_plan(eligibility)],
        )
        return None
    return _RetryPlan(message, trace, eligibility, old_id, raw_id)


async def handle_retry(
    data: dict,
    container: Any,
    msg_store: Any,
    conn_mgr: ConnectionManager,
    *,
    feedback_store: Any,
    confirmation_store: Any,
) -> tuple[str, dict] | None:
    """Undo the latest reply's reversible actions, then regenerate it in place.

    The caller holds the per-thread busy flag. Eligibility and the undo plan are
    decided here, on the server, from the recorded turn; a refusal happens before
    anything changes. The thread's turn lock is held from the final check through
    regeneration, so no follow-up turn lands between the undos and the rewind.
    Returns the gate to track when the retry pauses for a confirmation.
    """
    thread_id: str = data.get("thread_id") or ""
    first = await _prepare_retry(
        data, container, msg_store, conn_mgr, confirmation_store, thread_held=False
    )
    if first is None:
        return None
    async with container.hold_thread(thread_id):
        prepared = await _prepare_retry(
            data, container, msg_store, conn_mgr, confirmation_store, thread_held=True
        )
        if prepared is None:
            return None
        return await _retry_locked(
            prepared,
            thread_id,
            container,
            msg_store,
            conn_mgr,
            feedback_store=feedback_store,
            confirmation_store=confirmation_store,
        )


async def _retry_locked(
    prepared: _RetryPlan,
    thread_id: str,
    container: Any,
    msg_store: Any,
    conn_mgr: ConnectionManager,
    *,
    feedback_store: Any,
    confirmation_store: Any,
) -> tuple[str, dict] | None:
    from ze_memory.feedback_records import (
        FeedbackKind,
        FeedbackRecordDraft,
        feedback_contribution,
        submit_feedback_record,
    )

    message, trace, eligibility = (
        prepared.message,
        prepared.trace,
        prepared.eligibility,
    )
    old_id, raw_id = prepared.old_id, prepared.raw_id
    plan = eligibility.plan

    user_msg = await msg_store.previous_user_message(old_id)
    if user_msg is None or not user_msg.text:
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_failed",
            "Ze could not find the message to answer again.",
        )
        return None

    if not await container.retry_rewindable(thread_id):
        await _retry_error(
            conn_mgr,
            thread_id,
            raw_id,
            "retry_unavailable",
            "Ze can no longer rewind this conversation, so Retry cannot answer again. "
            "Nothing was changed.",
            reason_code="history_unavailable",
        )
        return None

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

    record = message.rollback
    if plan:
        record = await run_rollback(
            plan,
            message_id=old_id,
            thread_id=thread_id,
            session_id=thread_id,
            message_store=msg_store,
        )
        await publish_rollback(conn_mgr, thread_id, old_id, record)
        if record.state == "partial":
            await _retry_error(
                conn_mgr,
                thread_id,
                raw_id,
                "retry_partial",
                rollback_notice(record),
                rolled_back=True,
                rollback=record,
            )
            return None
    rolled_back = bool(undone_phrases(record))

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

    async def _failed(detail: str) -> None:
        if rolled_back and record is not None:
            moved = await move_rollback(
                msg_store,
                conn_mgr,
                thread_id,
                old_id,
                "rolled_back_retry_failed",
                record=record,
            )
            await _retry_error(
                conn_mgr,
                thread_id,
                raw_id,
                "retry_failed",
                rollback_notice(moved or record),
                rolled_back=True,
                rollback=moved or record,
            )
            return
        await _retry_error(conn_mgr, thread_id, raw_id, "retry_failed", detail)

    try:
        with bound_turn_context(thread_id):
            outcome = await container.invoke_retry_turn(
                thread_id,
                user_msg.text,
                replaces=old_id,
                config_extra=config_extra,
            )
    except RetryError as exc:
        log.warning("ws_retry_failed", error=str(exc))
        await _failed("Retry failed. The original reply is unchanged.")
        return None
    except Exception as exc:
        log.exception("ws_retry_error", error=str(exc))
        await _failed("Retry failed. The original reply is unchanged.")
        return None

    if outcome.interrupted:
        if rolled_back and record is not None:
            await move_rollback(
                msg_store,
                conn_mgr,
                thread_id,
                old_id,
                "rolled_back_awaiting_confirmation",
                record=record,
            )
        return await send_confirmation_request(
            conn_mgr,
            container,
            outcome,
            thread_id,
            confirmation_store=confirmation_store,
        )

    delivered = await deliver_retry_reply(
        container,
        msg_store,
        conn_mgr,
        thread_id=extract_thread_id(outcome.config) or thread_id,
        old_id=old_id,
        outcome=outcome,
        record=record,
    )
    if not delivered:
        await _failed("Retry failed. The original reply is unchanged.")
    return None
