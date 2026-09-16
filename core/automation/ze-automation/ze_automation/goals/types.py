from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from ze_agents.claims import ClaimKind, Provenance


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


@dataclass
class GoalSuggestion:
    id: UUID
    title: str
    objective: str
    rationale: str
    source_type: str
    source_ref: str
    status: SuggestionStatus
    suggested_at: datetime
    resolved_at: datetime | None = None
    created_goal_id: UUID | None = None


class GoalStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    AWAITING_GATE = "awaiting_gate"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MilestoneStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class GateStatus(StrEnum):
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    STOPPED = "stopped"
    REDIRECTED = "redirected"


@dataclass
class Goal:
    title: str
    objective: str
    success_condition: str
    status: GoalStatus = GoalStatus.PLANNING
    type: str = "custom"
    time_horizon: str = ""
    retrospective_text: str | None = None
    last_stuck_alert_at: datetime | None = None
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class PriorMilestoneOutput:
    goal_id: UUID
    goal_title: str
    milestone_id: UUID
    milestone_title: str
    output_snippet: str  # first 200 chars of milestone output
    completed_days_ago: int


@dataclass
class Milestone:
    goal_id: UUID
    title: str
    description: str
    sequence: int
    agent_hint: str | None = None
    intent: str = "execute"
    status: MilestoneStatus = MilestoneStatus.PENDING
    output: str = ""
    reuse_hint: str = ""
    id: UUID | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


@dataclass
class VerificationGate:
    goal_id: UUID
    after_sequence: int
    title: str
    status: GateStatus = GateStatus.PENDING
    context_summary: str = ""
    plan_summary: str = ""
    user_feedback: str = ""
    id: UUID | None = None
    fired_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None


class LearningStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    REVIEW_NEEDED = "review_needed"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"


class LearningEvidenceKind(StrEnum):
    ACTION_RECORD = "action_record"
    USER_CONFIRMATION = "user_confirmation"
    USER_CORRECTION = "user_correction"


class LearningEvidenceRole(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVES = "derives"


class LearningReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    CORRECT = "correct"
    DEFER = "defer"
    RETAIN = "retain"


class LearningPromotionState(StrEnum):
    PENDING = "pending"
    PROMOTED = "promoted"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class LearningEvidenceDraft:
    evidence_kind: LearningEvidenceKind
    role: LearningEvidenceRole
    excerpt: str
    action_record_id: UUID | None = None
    review_id: UUID | None = None
    execution_context_key: str | None = None


@dataclass
class LearningEvidence:
    id: UUID
    learning_id: UUID
    evidence_kind: LearningEvidenceKind
    role: LearningEvidenceRole
    excerpt: str
    action_record_id: UUID | None = None
    review_id: UUID | None = None
    execution_context_key: str | None = None
    created_at: datetime | None = None


@dataclass
class GoalLearning:
    goal_id: UUID
    content: str
    claim_kind: ClaimKind = ClaimKind.INFERENCE
    provenance: Provenance = Provenance.SYNTHESIZED
    confidence: float = 0.4
    status: LearningStatus = LearningStatus.PENDING_REVIEW
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    activated_at: datetime | None = None
    retracted_at: datetime | None = None
    superseded_by_id: UUID | None = None
    evidence: list[LearningEvidence] = field(default_factory=list)


@dataclass(frozen=True)
class GoalLearningSummary:
    id: UUID
    content: str
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float
    status: LearningStatus
    evidence_count: int
    promotion_state: LearningPromotionState | None
    review_needed: bool
    created_at: datetime | None = None


@dataclass(frozen=True)
class EligibleLearning:
    id: UUID
    content: str
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float
    evidence_summary: str
    relevance: float


@dataclass(frozen=True)
class PromotionEligibility:
    eligible: bool
    reason: str
    supporting_action_record_ids: tuple[UUID, ...]
    independent_context_count: int
    user_confirmed: bool
    unresolved_contradiction: bool
    permitted_claim_kind: ClaimKind


@dataclass
class LearningPromotion:
    learning_id: UUID
    state: LearningPromotionState
    id: UUID | None = None
    memory_fact_id: UUID | None = None
    eligibility_snapshot: dict | None = None
    failure_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ExecutionTrace:
    milestone_id: UUID
    goal_id: UUID
    seq: int
    tool_name: str
    args: dict
    result: str
    duration_ms: int
    success: bool
    error: str | None = None
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass
class StuckGoal:
    goal: Goal
    kind: Literal["active", "awaiting_gate"]
    idle_days: int
    last_milestone_title: str | None
    gate: VerificationGate | None


@dataclass
class GoalDetail:
    goal: "Goal"
    milestones: "list[Milestone]"
    gates: "list[VerificationGate]"
    learnings: "list[GoalLearningSummary]"


@dataclass
class GoalConvergence:
    overlapping_goal_id: UUID
    overlapping_goal_title: str
    overlap_description: str
    suggestion: str
