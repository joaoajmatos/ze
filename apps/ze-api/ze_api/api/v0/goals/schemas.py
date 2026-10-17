from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
)


class GoalListItem(BaseModel):
    id: UUIDType
    title: str
    objective: str
    status: str
    created_at: datetime
    milestones_done: int
    milestones_total: int
    next_milestone: str | None
    gate_id: UUIDType | None
    gate_title: str | None
    gate_open_since: datetime | None
    last_progress_at: datetime | None
    stuck_since: datetime | None


class GoalActionResponse(BaseModel):
    id: UUIDType
    status: str


class MilestoneResponse(BaseModel):
    id: UUIDType
    title: str
    description: str
    sequence: int
    status: str
    output: str | None
    reuse_hint: str | None
    completed_at: datetime | None
    created_at: datetime


class GateResponse(BaseModel):
    id: UUIDType
    after_sequence: int
    title: str
    status: str
    context_summary: str | None
    plan_summary: str | None
    user_feedback: str | None
    fired_at: datetime | None
    resolved_at: datetime | None


class LearningReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "correct", "defer"]
    rationale: str | None = None
    corrected_content: str | None = None


class LearningResponse(BaseModel):
    id: UUIDType
    content: str
    claim_kind: str
    provenance: str
    confidence: float
    status: str
    evidence_count: int
    promotion_state: str | None
    review_needed: bool
    created_at: datetime | None


class GoalDetailResponse(BaseModel):
    id: UUIDType
    title: str
    objective: str
    success_condition: str
    status: str
    type: str
    time_horizon: str | None
    learnings_summary: str | None
    retrospective_text: str | None
    created_at: datetime
    updated_at: datetime
    milestones: list[MilestoneResponse]
    gates: list[GateResponse]
    learnings: list[LearningResponse]


class ExecutionTraceResponse(BaseModel):
    id: UUIDType
    milestone_id: UUIDType
    goal_id: UUIDType
    seq: int
    tool_name: str
    args: dict
    result: str
    duration_ms: int
    success: bool
    error: str | None
    created_at: datetime
