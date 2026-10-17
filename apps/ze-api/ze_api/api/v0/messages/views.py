"""Read model for per-reply feedback and Retry eligibility (Phase 165).

Shared by the REST batch endpoint and the WebSocket retry handler so both decide
eligibility the same way, on the server.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ze_api.api.shared_schemas import RollbackRecordResponse
from ze_api.api.v0.messages.schemas import (
    FeedbackHistoryItem,
    FeedbackView,
    RetryEligibilityResponse,
    UndoPlanEntryResponse,
)
from ze_core.conversation.messages.types import Message, MessageTrace
from ze_core.conversation.retry import RetryEligibility, retry_eligibility
from ze_memory.feedback_records import FeedbackKind, FeedbackRecord

_CURRENT = {FeedbackKind.THUMBS_UP: "up", FeedbackKind.THUMBS_DOWN: "down"}
_RATINGS = (FeedbackKind.THUMBS_UP, FeedbackKind.THUMBS_DOWN, FeedbackKind.CLEARED)


@dataclass
class ThreadState:
    """What the server knows about a thread when it decides Retry eligibility."""

    latest_assistant_id: UUID | None
    busy: bool
    pending: bool


def current_rating(history: Iterable[FeedbackRecord]) -> str | None:
    latest: FeedbackRecord | None = None
    for record in history:
        if record.kind in _RATINGS:
            latest = record
    return _CURRENT.get(latest.kind) if latest is not None else None


async def thread_state(
    thread_id: str | None,
    *,
    message_store: Any,
    is_busy: Callable[[str], bool],
    confirmation_store: Any,
) -> ThreadState:
    if not thread_id:
        return ThreadState(latest_assistant_id=None, busy=False, pending=False)
    latest = await message_store.latest_assistant_id(thread_id)
    busy = bool(is_busy(thread_id))
    pending = bool(await confirmation_store.get_pending_for_thread(thread_id))
    return ThreadState(latest_assistant_id=latest, busy=busy, pending=pending)


def evaluate_retry(
    message: Message, trace: MessageTrace | None, state: ThreadState
) -> RetryEligibility:
    return retry_eligibility(
        message,
        trace,
        latest_assistant_id=state.latest_assistant_id,
        thread_busy=state.busy,
        pending=state.pending,
        rollback=message.rollback,
    )


def public_plan(eligibility: RetryEligibility) -> list[UndoPlanEntryResponse]:
    """The plan as the client sees it: no agent, no undo arguments."""
    return [
        UndoPlanEntryResponse(
            entry_id=e.entry_id,
            tool=e.tool,
            effect_phrase=e.effect_phrase,
            undo_note=e.undo_note or None,
        )
        for e in eligibility.plan
    ]


def public_rollback(message: Message) -> RollbackRecordResponse | None:
    if message.rollback is None:
        return None
    return RollbackRecordResponse.model_validate(message.rollback)


def build_view(
    message: Message,
    history: list[FeedbackRecord],
    trace: MessageTrace | None,
    state: ThreadState,
) -> FeedbackView:
    eligibility = evaluate_retry(message, trace, state)
    return FeedbackView(
        message_id=message.id,
        current=current_rating(history),
        history=[
            FeedbackHistoryItem(kind=r.kind.value, occurred_at=r.occurred_at)
            for r in history
        ],
        retry=RetryEligibilityResponse(
            available=eligibility.available,
            reason_code=eligibility.reason_code.value
            if eligibility.reason_code
            else None,
            reason_text=eligibility.reason_text,
            plan=public_plan(eligibility),
        ),
        rollback=public_rollback(message),
        replaces=message.replaces,
        replaced_by=message.replaced_by,
        trace_present=trace is not None,
    )


async def build_views(
    message_ids: list[UUID],
    *,
    message_store: Any,
    feedback_store: Any,
    conn_mgr: Any,
    turn_lock: Any,
    confirmation_store: Any,
) -> list[FeedbackView]:
    """One view per stored assistant message among `message_ids`, in request order."""
    message_ids = list(dict.fromkeys(message_ids))
    messages = await message_store.get_messages(message_ids)
    assistant = [
        mid
        for mid in message_ids
        if mid in messages and messages[mid].role == "assistant"
    ]
    if not assistant:
        return []
    traces = await message_store.get_traces(assistant)
    history = await feedback_store.list_for_messages(assistant)
    states: dict[str | None, ThreadState] = {}
    views: list[FeedbackView] = []
    for mid in assistant:
        message = messages[mid]
        if message.thread_id not in states:
            states[message.thread_id] = await thread_state(
                message.thread_id,
                message_store=message_store,
                is_busy=lambda tid: conn_mgr.is_busy(tid) or turn_lock.is_locked(tid),
                confirmation_store=confirmation_store,
            )
        views.append(
            build_view(
                message,
                history.get(mid, []),
                traces.get(mid),
                states[message.thread_id],
            )
        )
    return views
