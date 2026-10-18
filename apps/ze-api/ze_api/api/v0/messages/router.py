from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_agents.errors import FeedbackRecordIdempotencyConflictError

from ze_api.api.deps import (
    get_confirmation_store,
    get_connection_manager,
    get_feedback_store,
    get_message_store,
    get_turn_lock,
    require_api_key,
)
from ze_api.api.v0.messages.schemas import (
    FeedbackView,
    MessageFeedbackResponse,
    MessageSchema,
    MessageTraceEntry,
    MessageTraceResponse,
    MessageTracesResponse,
    SetMessageFeedbackRequest,
)
from ze_api.api.v0.messages.views import (
    build_view,
    build_views,
    current_rating,
    thread_state,
)
from ze_core.conversation.messages import MessageStore
from ze_memory.feedback_records import (
    FeedbackKind,
    FeedbackRecordDraft,
    feedback_contribution,
    submit_feedback_record,
)

router = APIRouter(
    prefix="/messages", tags=["messages"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "",
    response_model=list[MessageSchema],
    operation_id="listMessages",
    summary="Load message history",
    description=(
        "Returns messages after `since` (ISO 8601), oldest-first. Max 200. "
        "Pass `thread_id` to load messages for a specific session. Replies "
        "replaced by a retry are hidden unless `include_superseded` is true."
    ),
)
async def list_messages(
    since: datetime | None = Query(
        default=None, description="Load messages after this timestamp (ISO 8601)"
    ),
    thread_id: str | None = Query(
        default=None, description="Filter by session thread ID"
    ),
    limit: int = Query(default=100, le=200),
    include_superseded: bool = Query(
        default=False,
        description="Include replies that a retry replaced (hidden by default)",
    ),
    store: MessageStore = Depends(get_message_store),
) -> list[MessageSchema]:
    if thread_id is not None:
        messages = await store.list_by_thread(
            thread_id, limit, include_superseded=include_superseded
        )
    elif since is not None:
        messages = await store.list_since(
            since, limit, include_superseded=include_superseded
        )
    else:
        since_default = datetime.fromisoformat("2000-01-01T00:00:00+00:00")
        messages = await store.list_since(
            since_default, limit, include_superseded=include_superseded
        )
    return [MessageSchema.model_validate(m.__dict__) for m in messages]


def _trace_to_response(trace) -> MessageTraceResponse:
    return MessageTraceResponse(
        agent=trace.agent,
        routing_method=trace.routing_method,
        confidence=trace.confidence,
        score_gap=trace.score_gap,
        is_compound=trace.is_compound,
        subtasks=trace.subtasks,
        memory_chunks=[
            {
                "text": c.text,
                "score": c.score,
                "source": c.source,
                "extraction_confidence": c.extraction_confidence,
            }
            for c in trace.memory_chunks
        ],
        tool_calls=[
            {
                "name": t.name,
                "result_snippet": t.result_snippet,
                "duration_ms": t.duration_ms,
                "success": t.success,
                "access": t.access,
                "reversibility": t.reversibility,
                "undo_tool": t.undo_tool,
                "gate": t.gate,
                "effect_phrase": t.effect_phrase,
                "agent": t.agent,
                "call_index": t.call_index,
            }
            for t in trace.tool_calls
        ],
        total_duration_ms=trace.total_duration_ms,
        skills_used=[
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "source": s.source,
                "trigger": s.trigger,
                "similarity": s.similarity,
                "script_ran": getattr(s, "script_ran", False),
                "below_floor": getattr(s, "below_floor", False),
            }
            for s in getattr(trace, "skills_used", [])
        ],
        workspace=_workspace_to_response(getattr(trace, "workspace", None)),
        procedure=_procedure_to_response(getattr(trace, "procedure", None)),
        conductor_hint=getattr(trace, "conductor_hint", None),
        conductor_ledger=list(getattr(trace, "conductor_ledger", None) or []),
        judgments=_judgments_to_response(getattr(trace, "judgments", None)),
        sources=[
            {"url": s.url, "title": s.title} for s in getattr(trace, "sources", [])
        ],
        effects_known=bool(getattr(trace, "effects_known", False)),
        compaction=(
            {
                "span_start": trace.compaction.span_start,
                "span_end": trace.compaction.span_end,
            }
            if getattr(trace, "compaction", None)
            else None
        ),
        resume_recap_applied=bool(getattr(trace, "resume_recap_applied", False)),
        rollback=getattr(trace, "rollback", None),
        loop_offer_ids=list(getattr(trace, "loop_offer_ids", None) or []),
        write_confirmations=[
            _write_confirmation_row(row)
            for row in getattr(trace, "write_confirmations", None) or []
        ],
        tier=_tier_to_response(getattr(trace, "tier", None)),
        screen=_screen_to_response(getattr(trace, "screen", None)),
        input=_dataclass_to_response(getattr(trace, "input", None)),
    )


def _write_confirmation_row(row: dict) -> dict:
    return {
        "request_id": str(row.get("request_id", "")),
        "round": int(row.get("round", 1)),
        "item_id": str(row.get("item_id", "")),
        "agent": str(row.get("agent", "")),
        "tool": row.get("tool"),
        "effect": row.get("effect"),
        "summary": str(row.get("summary", "")),
        "outcome": row.get("outcome", "denied"),
    }


def _dataclass_to_response(value) -> dict | None:
    return asdict(value) if value is not None else None


def _screen_to_response(screen) -> dict | None:
    return asdict(screen) if screen is not None else None


def _tier_to_response(tier) -> dict | None:
    if tier is None:
        return None
    return {
        "agent": tier.agent,
        "tier": tier.tier,
        "decided_by": tier.decided_by,
        "model": tier.model,
    }


def _judgments_to_response(judgments) -> list[dict]:
    rows = []
    for item in judgments or []:
        rows.append(
            {
                "question_id": item.question_id,
                "kind": item.kind,
                "latency_ms": item.latency_ms,
                "answer": item.answer,
                "probabilities": item.probabilities,
                "peakedness": item.peakedness,
                "model": item.model,
                "input_tokens": item.input_tokens,
                "consumed": item.consumed,
                "skip_reason": item.skip_reason,
            }
        )
    return rows


def _workspace_to_response(workspace) -> dict | None:
    if workspace is None:
        return None
    return {
        "runs": list(workspace.runs or []),
        "files": list(workspace.files or []),
        "script_ran": bool(workspace.script_ran),
        "unavailable": bool(workspace.unavailable),
        "planned": workspace.planned,
    }


def _procedure_to_response(procedure) -> dict | None:
    if procedure is None:
        return None
    return {
        "invocation_id": procedure.invocation_id,
        "procedure_id": procedure.procedure_id,
        "version_id": procedure.version_id,
    }


@router.get(
    "/traces",
    response_model=MessageTracesResponse,
    operation_id="getMessageTraces",
    summary="Batch get message traces",
    description=(
        "Returns execution traces for multiple assistant messages in one request. "
        "Omitted IDs have no trace (user messages or pre-Phase-89)."
    ),
)
async def get_message_traces(
    ids: list[UUID] = Query(
        default=[], max_length=100, description="Message IDs to fetch traces for"
    ),
    store: MessageStore = Depends(get_message_store),
) -> MessageTracesResponse:
    if not ids:
        return MessageTracesResponse(traces=[])
    traces = await store.get_traces(ids)
    return MessageTracesResponse(
        traces=[
            MessageTraceEntry(
                message_id=message_id,
                trace=_trace_to_response(trace),
            )
            for message_id, trace in traces.items()
        ]
    )


@router.get(
    "/{message_id}/trace",
    response_model=MessageTraceResponse,
    operation_id="getMessageTrace",
    summary="Get message trace",
    description=(
        "Returns the execution trace for an AI message — routing decision, "
        "memory chunks retrieved, and tool calls made. 404 for user messages "
        "or messages without a trace (pre-Phase-89)."
    ),
)
async def get_message_trace(
    message_id: UUID,
    store: MessageStore = Depends(get_message_store),
) -> MessageTraceResponse:
    trace = await store.get_trace(message_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _trace_to_response(trace)


_KIND_FOR_RATING = {
    "up": FeedbackKind.THUMBS_UP,
    "down": FeedbackKind.THUMBS_DOWN,
    "none": FeedbackKind.CLEARED,
}


@router.put(
    "/{message_id}/feedback",
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
    "/feedback",
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
