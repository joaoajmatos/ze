from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ze_automation.goals.types import LearningReviewDecision
from ze_api.api.dependencies import require_api_key
from ze_api.api.schemas import (
    ExecutionTraceResponse,
    GateResponse,
    GoalActionResponse,
    GoalDetailResponse,
    GoalListItem,
    LearningDetailResponse,
    LearningEvidenceSummary,
    LearningPromotionResponse,
    LearningResponse,
    LearningReviewRequest,
    MilestoneResponse,
)

router = APIRouter(tags=["goals"], dependencies=[Depends(require_api_key)])


def _learning_response(row) -> LearningResponse:
    return LearningResponse(
        id=row.id,
        content=row.content,
        claim_kind=row.claim_kind.value,
        provenance=row.provenance.value,
        confidence=row.confidence,
        status=row.status.value,
        evidence_count=row.evidence_count,
        promotion_state=row.promotion_state.value if row.promotion_state else None,
        review_needed=row.review_needed,
        created_at=row.created_at,
    )


@router.get(
    "/goals",
    response_model=list[GoalListItem],
    operation_id="listGoals",
    summary="List goals for the web client",
    description=(
        "Returns planning, active, awaiting-gate, and paused goals for the web client goals screen."
    ),
)
async def list_goals(request: Request) -> list[GoalListItem]:
    store = request.app.state.container._plugin_stores.get("goal_store")
    if store is None:
        return []

    goals = await store.list_for_display()
    return [
        GoalListItem(
            id=goal.id,
            title=goal.title,
            objective=goal.objective,
            status=goal.status.value,
            created_at=goal.created_at,
        )
        for goal in goals
        if goal.id is not None and goal.created_at is not None
    ]


@router.get(
    "/goals/{goal_id}",
    response_model=GoalDetailResponse,
    operation_id="getGoalDetail",
    summary="Get goal detail",
    description="Returns full goal detail including milestones, verification gates, and learnings.",
)
async def get_goal_detail(request: Request, goal_id: UUID) -> GoalDetailResponse:
    store = request.app.state.container._plugin_stores.get("goal_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Goal engine unavailable")

    detail = await store.get_goal_detail(goal_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    g = detail.goal
    return GoalDetailResponse(
        id=g.id,
        title=g.title,
        objective=g.objective,
        success_condition=g.success_condition,
        status=g.status.value,
        type=g.type,
        time_horizon=g.time_horizon or None,
        learnings_summary=None,
        retrospective_text=g.retrospective_text,
        created_at=g.created_at,
        updated_at=g.updated_at,
        milestones=[
            MilestoneResponse(
                id=m.id,
                title=m.title,
                description=m.description,
                sequence=m.sequence,
                status=m.status.value,
                output=m.output or None,
                reuse_hint=m.reuse_hint or None,
                completed_at=m.completed_at,
                created_at=m.created_at,
            )
            for m in detail.milestones
        ],
        gates=[
            GateResponse(
                id=gate.id,
                after_sequence=gate.after_sequence,
                title=gate.title,
                status=gate.status.value,
                context_summary=gate.context_summary or None,
                plan_summary=gate.plan_summary or None,
                user_feedback=gate.user_feedback or None,
                fired_at=gate.fired_at,
                resolved_at=gate.resolved_at,
            )
            for gate in detail.gates
        ],
        learnings=[_learning_response(lr) for lr in detail.learnings],
    )


@router.get(
    "/goals/{goal_id}/learnings",
    response_model=list[LearningResponse],
    operation_id="listGoalLearnings",
    summary="List goal learnings",
    description="Returns evidence-backed learning summaries. History includes retracted and superseded claims.",
)
async def list_goal_learnings(
    request: Request,
    goal_id: UUID,
    include_history: bool = Query(default=False),
) -> list[LearningResponse]:
    store = request.app.state.container._plugin_stores.get("goal_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Goal engine unavailable")
    rows = await store.list_goal_learnings(goal_id, include_history=include_history)
    return [_learning_response(lr) for lr in rows]


@router.get(
    "/goals/{goal_id}/learnings/{learning_id}",
    response_model=LearningDetailResponse,
    operation_id="getGoalLearning",
    summary="Get a goal learning",
    description="Returns one learning with redaction-safe evidence summaries.",
)
async def get_goal_learning(
    request: Request, goal_id: UUID, learning_id: UUID
) -> LearningDetailResponse:
    store = request.app.state.container._plugin_stores.get("goal_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Goal engine unavailable")
    learning = await store.get_learning(learning_id)
    if learning is None or learning.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Learning not found")
    summary = await store.list_goal_learnings(goal_id, include_history=True)
    match = next((row for row in summary if row.id == learning.id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Learning not found")
    base = _learning_response(match)
    return LearningDetailResponse(
        **base.model_dump(),
        evidence=[
            LearningEvidenceSummary(
                id=item.id,
                evidence_kind=item.evidence_kind.value,
                role=item.role.value,
                excerpt=item.excerpt,
                action_record_id=item.action_record_id,
                execution_context_key=item.execution_context_key,
            )
            for item in learning.evidence
        ],
    )


@router.post(
    "/goals/{goal_id}/learnings/{learning_id}/review",
    response_model=LearningResponse,
    operation_id="reviewGoalLearning",
    summary="Review a goal learning",
    description="Approve, reject, correct, or defer an evidence-backed learning.",
)
async def review_goal_learning(
    request: Request,
    goal_id: UUID,
    learning_id: UUID,
    body: LearningReviewRequest,
) -> LearningResponse:
    store = request.app.state.container._plugin_stores.get("goal_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Goal engine unavailable")
    try:
        decision = LearningReviewDecision(body.decision)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid review decision") from exc
    learning = await store.review_learning(
        learning_id,
        decision,
        rationale=body.rationale,
        corrected_content=body.corrected_content,
    )
    if learning is None or learning.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Learning not found")
    summary = await store.list_goal_learnings(goal_id, include_history=True)
    match = next((row for row in summary if row.id == learning.id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Learning not found")
    return _learning_response(match)


@router.post(
    "/goals/{goal_id}/learnings/{learning_id}/promote",
    response_model=LearningPromotionResponse,
    operation_id="promoteGoalLearning",
    summary="Promote a goal learning",
    description=(
        "Publishes a user-confirmed FACT through the licensed perception-fact path. "
        "Inferences remain labeled learnings and are not written to memory_facts."
    ),
)
async def promote_goal_learning(
    request: Request, goal_id: UUID, learning_id: UUID
) -> LearningPromotionResponse:
    store = request.app.state.container._plugin_stores.get("goal_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Goal engine unavailable")
    learning = await store.get_learning(learning_id)
    if learning is None or learning.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Learning not found")
    promotion = await store.promote_learning(learning_id)
    return LearningPromotionResponse(
        id=promotion.id,
        learning_id=promotion.learning_id,
        state=promotion.state.value,
        memory_fact_id=promotion.memory_fact_id,
        failure_reason=promotion.failure_reason,
        created_at=promotion.created_at,
    )


@router.get(
    "/goals/{goal_id}/traces",
    response_model=list[ExecutionTraceResponse],
    operation_id="listGoalTraces",
    summary="List goal execution traces",
    description="Returns execution traces for all milestones of a goal, ordered by seq ASC.",
)
async def list_goal_traces(
    request: Request,
    goal_id: UUID,
    milestone_id: UUID | None = Query(
        default=None, description="Filter to a single milestone"
    ),
    limit: int = Query(default=100, ge=1, le=500, description="Max rows"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> list[ExecutionTraceResponse]:
    store = request.app.state.container._plugin_stores.get("goal_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Goal engine unavailable")

    traces = await store.list_traces(
        goal_id=goal_id,
        milestone_id=milestone_id,
        limit=limit,
        offset=offset,
    )
    return [
        ExecutionTraceResponse(
            id=t.id,
            milestone_id=t.milestone_id,
            goal_id=t.goal_id,
            seq=t.seq,
            tool_name=t.tool_name,
            args=t.args,
            result=t.result,
            duration_ms=t.duration_ms,
            success=t.success,
            error=t.error,
            created_at=t.created_at,
        )
        for t in traces
    ]


@router.post(
    "/goals/{goal_id}/start",
    response_model=GoalActionResponse,
    operation_id="startGoal",
    summary="Start a planned goal",
    description="Activates a goal in planning status and begins milestone execution.",
)
async def start_goal(request: Request, goal_id: UUID) -> GoalActionResponse:
    store = request.app.state.container._plugin_stores.get("goal_store")
    executor = request.app.state.container._plugin_stores.get("goal_executor")
    if store is None or executor is None:
        raise HTTPException(status_code=503, detail="Goal engine unavailable")

    if not await executor.approve_plan(goal_id):
        raise HTTPException(
            status_code=404,
            detail="Goal not found or not awaiting plan approval",
        )

    goal = await store.get_goal(goal_id)
    mgr = request.app.state.container.connection_manager
    await mgr.send_frame({"type": "refresh", "screen": "goals"})

    return GoalActionResponse(
        id=goal_id,
        status=goal.status.value if goal is not None else "active",
    )
