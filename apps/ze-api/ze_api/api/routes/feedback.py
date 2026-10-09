from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_agents.errors import FeedbackRecordIdempotencyConflictError
from ze_api.api.dependencies import (
    get_confirmation_store,
    get_connection_manager,
    get_feedback_store,
    get_message_store,
    get_turn_lock,
    require_api_key,
)
from ze_api.api.schemas import (
    FeedbackView,
    MessageFeedbackResponse,
    SetMessageFeedbackRequest,
)
from ze_api.feedback_views import (
    build_view,
    build_views,
    current_rating,
    thread_state,
)
from ze_memory.feedback_records import (
    FeedbackKind,
    FeedbackRecordDraft,
    feedback_contribution,
    submit_feedback_record,
)

router = APIRouter(tags=["messages"], dependencies=[Depends(require_api_key)])

_KIND_FOR_RATING = {
    "up": FeedbackKind.THUMBS_UP,
    "down": FeedbackKind.THUMBS_DOWN,
    "none": FeedbackKind.CLEARED,
}


@router.put(
    "/messages/{message_id}/feedback",
    response_model=FeedbackView,
    operation_id="setMessageFeedback",
    summary="Rate an assistant reply",
    description=(
        "Sets, changes, or clears the thumbs rating on a stored assistant message. "
        "Every change appends one immutable feedback record; the current rating is "
        "the latest one. Repeating the same `idempotency_key` appends nothing. "
        "Feedback is evidence about the reply, never a fact about the user. "
        "404 for an unknown message or a user message."
    ),
)
async def set_message_feedback(
    message_id: UUID,
    body: SetMessageFeedbackRequest,
    message_store=Depends(get_message_store),
    feedback_store=Depends(get_feedback_store),
    conn_mgr=Depends(get_connection_manager),
    turn_lock=Depends(get_turn_lock),
    confirmation_store=Depends(get_confirmation_store),
) -> FeedbackView:
    message = await message_store.get_message(message_id)
    if message is None or message.role != "assistant":
        raise HTTPException(status_code=404, detail="Assistant message not found")

    trace = await message_store.get_trace(message_id)
    history = await feedback_store.history(message_id)
    if body.rating != (current_rating(history) or "none"):
        draft = FeedbackRecordDraft(
            idempotency_key=f"feedback:{message_id}:{body.idempotency_key}",
            message_id=message_id,
            thread_id=message.thread_id or "",
            kind=_KIND_FOR_RATING[body.rating],
            occurred_at=datetime.now(timezone.utc),
            trace_present=trace is not None,
        )
        try:
            await submit_feedback_record(feedback_store, feedback_contribution(draft))
        except FeedbackRecordIdempotencyConflictError:
            raise HTTPException(
                status_code=409,
                detail="idempotency_key was already used for a different rating",
            )
        history = await feedback_store.history(message_id)

    state = await thread_state(
        message.thread_id,
        message_store=message_store,
        is_busy=lambda tid: conn_mgr.is_busy(tid) or turn_lock.is_locked(tid),
        confirmation_store=confirmation_store,
    )
    return build_view(message, history, trace, state)


@router.get(
    "/messages/feedback",
    response_model=MessageFeedbackResponse,
    operation_id="getMessageFeedback",
    summary="Batch get reply feedback and Retry eligibility",
    description=(
        "Returns the current rating, rating history, replacement links, and Retry "
        "eligibility for up to 100 assistant messages in one request. User messages "
        "are omitted. Eligibility is decided on the server from the recorded turn."
    ),
)
async def get_message_feedback(
    ids: list[UUID] = Query(
        default=[], max_length=100, description="Assistant message IDs"
    ),
    message_store=Depends(get_message_store),
    feedback_store=Depends(get_feedback_store),
    conn_mgr=Depends(get_connection_manager),
    turn_lock=Depends(get_turn_lock),
    confirmation_store=Depends(get_confirmation_store),
) -> MessageFeedbackResponse:
    views = await build_views(
        list(dict.fromkeys(ids)),
        message_store=message_store,
        feedback_store=feedback_store,
        conn_mgr=conn_mgr,
        turn_lock=turn_lock,
        confirmation_store=confirmation_store,
    )
    return MessageFeedbackResponse(items=views)
