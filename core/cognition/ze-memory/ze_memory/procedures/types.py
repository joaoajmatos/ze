from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef


class ProcedureSourceKind(StrEnum):
    GOAL = "goal"
    WORKFLOW = "workflow"
    WORKSPACE_RUN = "workspace_run"
    ACTION_PATTERN = "action_pattern"
    USER_INSTRUCTION = "user_instruction"
    REFLECTION = "reflection"
    SKILL = "skill"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class IdentityStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class VersionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"
    RETIRED = "retired"


class ProcedureAdmissionDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"
    WITHDRAW = "withdraw"


class ProcedureOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    ABANDONED = "abandoned"


class LifecycleEventKind(StrEnum):
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    ADMITTED = "admitted"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"
    RESTORED = "restored"
    RETIRED = "retired"
    FEEDBACK_RECORDED = "feedback_recorded"
    DISCARDED_PROVISIONAL = "discarded_provisional"


class ProvisionalStatus(StrEnum):
    OPEN = "open"
    SUBMITTED = "submitted"
    DISCARDED = "discarded"


@dataclass(frozen=True)
class LearningRef:
    learning_id: UUID


@dataclass
class ProcedureIdentity:
    canonical_name: str
    status: IdentityStatus = IdentityStatus.ACTIVE
    id: UUID | None = None
    active_version_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProcedureCandidate:
    source_kind: ProcedureSourceKind
    provenance: Provenance
    name: str
    trigger: str
    preconditions: list[str]
    steps: list[str]
    success_criteria: list[str]
    limits: list[str] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    learning_refs: list[LearningRef] = field(default_factory=list)
    proposed_identity_id: UUID | None = None
    workspace_run_approved: bool = False
    status: CandidateStatus = CandidateStatus.PENDING
    id: UUID | None = None
    submitted_at: datetime | None = None
    resolved_at: datetime | None = None


@dataclass
class ProcedureAdmission:
    candidate_id: UUID
    decision: ProcedureAdmissionDecision
    reason: str
    reviewer: str
    review_evidence_refs: list[EvidenceRef] = field(default_factory=list)
    review_learning_refs: list[LearningRef] = field(default_factory=list)
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass
class ProcedureVersion:
    procedure_id: UUID
    version_number: int
    name: str
    trigger: str
    preconditions: list[str]
    steps: list[str]
    success_criteria: list[str]
    provenance: Provenance
    status: VersionStatus = VersionStatus.ACTIVE
    limits: list[str] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    learning_refs: list[LearningRef] = field(default_factory=list)
    supersedes_version_id: UUID | None = None
    superseded_by_version_id: UUID | None = None
    admission_id: UUID | None = None
    id: UUID | None = None
    created_at: datetime | None = None
    ended_at: datetime | None = None


@dataclass
class ProcedureFeedback:
    procedure_version_id: UUID
    action_record_id: UUID
    outcome: ProcedureOutcome
    summary: str
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    learning_refs: list[LearningRef] = field(default_factory=list)
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass
class ProcedureLifecycleEvent:
    kind: LifecycleEventKind
    reason: str
    identity_id: UUID | None = None
    candidate_id: UUID | None = None
    version_id: UUID | None = None
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    learning_refs: list[LearningRef] = field(default_factory=list)
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass
class ProvisionalProcedure:
    goal_id: UUID
    candidate: ProcedureCandidate
    execution_id: UUID | None = None
    status: ProvisionalStatus = ProvisionalStatus.OPEN
    resolution_reason: str | None = None
    id: UUID | None = None


@dataclass
class ProcedureAdmissionResult:
    candidate: ProcedureCandidate
    admission: ProcedureAdmission
    version: ProcedureVersion | None = None
    identity: ProcedureIdentity | None = None


@dataclass
class ProcedureRollbackResult:
    identity: ProcedureIdentity
    restored_version: ProcedureVersion | None
    retired: bool


class MatchState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    NOT_RELEVANT = "not_relevant"


class InvocationState(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcedureInvocationOrigin(StrEnum):
    AGENT = "agent"
    PLANNER = "planner"


class CapabilityDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class ProcedureActionOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_EXECUTED = "not_executed"


@dataclass
class ProcedureTaskContext:
    caller: str
    task_text: str
    available_facts: list[str] = field(default_factory=list)
    goal_id: UUID | None = None
    workflow_id: UUID | None = None
    thread_id: str | None = None


@dataclass
class ProcedureMatch:
    procedure_id: UUID
    version_id: UUID
    version_number: int
    name: str
    trigger: str
    steps: list[str]
    state: MatchState
    matched_trigger: str
    satisfied_preconditions: list[str]
    unmet_preconditions: list[str]
    effective_tool_names: frozenset[str] = field(default_factory=frozenset)
    procedure_relevant_tools: frozenset[str] = field(default_factory=frozenset)


@dataclass
class ProcedureInvocation:
    procedure_id: UUID
    version_id: UUID
    origin: ProcedureInvocationOrigin
    caller: str
    state: InvocationState = InvocationState.STARTED
    task_context_ref: str | None = None
    outcome_id: UUID | None = None
    id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class ProcedureActionLink:
    invocation_id: UUID
    procedure_id: UUID
    version_id: UUID
    step_ref: str
    capability_decision: CapabilityDecision
    outcome: ProcedureActionOutcome
    action_trace_ref: str | None = None
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass
class ProcedureOutcomeFeedback:
    invocation_id: UUID
    procedure_id: UUID
    version_id: UUID
    outcome: ProcedureOutcome
    summary: str
    action_link_ids: list[UUID] = field(default_factory=list)
    id: UUID | None = None
    submitted_at: datetime | None = None

