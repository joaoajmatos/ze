from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal, Union
from uuid import UUID as UUIDType
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)


# ── REST: health ──────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: Literal["ok"]


# ── REST: sessions ────────────────────────────────────────────────────────────


class SessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    preview: str | None
    title_source: Literal["user", "generated"] | None = None
    created_at: datetime
    last_active_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionSchema]
    next_before: datetime | None


class SessionSearchResult(BaseModel):
    id: str
    title: str | None
    preview: str | None
    title_source: Literal["user", "generated"] | None = None
    created_at: datetime
    last_active_at: datetime
    match_source: Literal["message", "metadata", "summary"]
    snippet: str | None
    rank: float


# ── REST: retry rollback (Phase 180) ──────────────────────────────────────────

RollbackOutcomeLiteral = Literal["undone", "failed", "not_attempted"]
RollbackStateLiteral = Literal[
    "partial",
    "rolled_back_awaiting_confirmation",
    "rolled_back_retry_failed",
    "superseded",
]


class UndoPlanEntryResponse(BaseModel):
    entry_id: str
    tool: str
    effect_phrase: str
    undo_note: str | None = None


class RollbackEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: str
    tool: str
    effect_phrase: str
    outcome: RollbackOutcomeLiteral
    at: str | None = None
    failure_code: str | None = None


class RollbackRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: RollbackStateLiteral
    entries: list[RollbackEntryResponse] = []
    replaced_by: str | None = None


class RollbackTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    replaces: str
    entries: list[RollbackEntryResponse] = []


# ── REST: messages ────────────────────────────────────────────────────────────


class MessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUIDType
    role: Literal["user", "assistant"]
    text: str | None
    components: list[dict[str, Any]]
    read: bool
    thread_id: str | None
    created_at: datetime
    replaces: UUIDType | None = None
    replaced_by: UUIDType | None = None
    rollback: RollbackRecordResponse | None = None


# ── REST: message trace ───────────────────────────────────────────────────────


class MemoryChunkTraceResponse(BaseModel):
    text: str
    score: float
    source: str
    extraction_confidence: float | None = None


class ToolCallTraceResponse(BaseModel):
    name: str
    result_snippet: str
    duration_ms: int
    success: bool
    access: Literal["read", "write", "delegate", "unknown"] = "unknown"
    reversibility: Literal["reversible", "irreversible"] | None = None
    undo_tool: str | None = None
    gate: Literal[
        "none",
        "approved",
        "pre_approved",
        "denied",
        "refused",
        "refused_over_cap",
        "expired",
        "duplicate",
    ] = "none"
    effect_phrase: str | None = None


class SkillUsageTraceResponse(BaseModel):
    skill_id: str
    name: str
    source: str
    trigger: str
    similarity: float | None = None
    script_ran: bool = False
    below_floor: bool = False


class ProcedureUsageTraceResponse(BaseModel):
    invocation_id: str
    procedure_id: str
    version_id: str


class ConductorLedgerEntryResponse(BaseModel):
    agent: str
    status: str
    request_id: str | None = None


class WorkspaceRunTraceResponse(BaseModel):
    command: str
    success: bool
    status: Literal["in_progress"] | None = None
    id: str | None = None


class WorkspaceFileTraceResponse(BaseModel):
    path: str
    op: Literal["read", "write", "delete", "ingest"]


class WorkspaceUsageTraceResponse(BaseModel):
    runs: list[WorkspaceRunTraceResponse] = []
    files: list[WorkspaceFileTraceResponse] = []
    script_ran: bool = False
    unavailable: bool = False
    planned: list[str] | None = None


class JudgmentTraceResponse(BaseModel):
    question_id: str
    kind: str
    latency_ms: int
    answer: str | float | None = None
    probabilities: dict[str, float] | None = None
    peakedness: float | None = None
    model: str | None = None
    input_tokens: int | None = None
    consumed: bool = False
    skip_reason: str | None = None


class CompactionTraceResponse(BaseModel):
    span_start: int
    span_end: int


class SourceTraceResponse(BaseModel):
    url: str
    title: str = ""


class WriteConfirmationOutcomeResponse(BaseModel):
    request_id: str
    round: int
    item_id: str
    agent: str
    tool: str | None = None
    effect: str | None = None
    summary: str = ""
    outcome: Literal[
        "approved",
        "edited",
        "pre_approved",
        "denied",
        "timed_out",
        "superseded",
        "refused",
    ]


class MessageTraceResponse(BaseModel):
    agent: str
    routing_method: str
    confidence: float
    score_gap: float
    is_compound: bool
    subtasks: list[str]
    memory_chunks: list[MemoryChunkTraceResponse]
    tool_calls: list[ToolCallTraceResponse]
    total_duration_ms: int
    skills_used: list[SkillUsageTraceResponse] = []
    workspace: WorkspaceUsageTraceResponse | None = None
    procedure: ProcedureUsageTraceResponse | None = None
    conductor_hint: list[dict[str, str]] | None = None
    conductor_ledger: list[ConductorLedgerEntryResponse] = []
    judgments: list[JudgmentTraceResponse] = []
    sources: list[SourceTraceResponse] = []
    effects_known: bool = False
    compaction: CompactionTraceResponse | None = None
    resume_recap_applied: bool = False
    rollback: RollbackTraceResponse | None = None
    loop_offer_ids: list[str] = []
    write_confirmations: list[WriteConfirmationOutcomeResponse] = []


class MessageTraceEntry(BaseModel):
    message_id: UUIDType
    trace: MessageTraceResponse


class MessageTracesResponse(BaseModel):
    traces: list[MessageTraceEntry]


# ── REST: message feedback (Phase 165) ────────────────────────────────────────

FeedbackRating = Literal["up", "down", "none"]
FeedbackHistoryKind = Literal["thumbs_up", "thumbs_down", "cleared", "retry_requested"]


class SetMessageFeedbackRequest(BaseModel):
    rating: FeedbackRating
    idempotency_key: str = Field(min_length=1, max_length=128)


class FeedbackHistoryItem(BaseModel):
    kind: FeedbackHistoryKind
    occurred_at: datetime


class RetryEligibilityResponse(BaseModel):
    available: bool
    reason_code: str | None = None
    reason_text: str | None = None
    plan: list[UndoPlanEntryResponse] = []


class FeedbackView(BaseModel):
    message_id: UUIDType
    current: Literal["up", "down"] | None = None
    history: list[FeedbackHistoryItem] = []
    retry: RetryEligibilityResponse
    replaces: UUIDType | None = None
    replaced_by: UUIDType | None = None
    trace_present: bool
    rollback: RollbackRecordResponse | None = None


class MessageFeedbackResponse(BaseModel):
    items: list[FeedbackView]


# ── REST: memory ──────────────────────────────────────────────────────────────


class FactDigestItem(BaseModel):
    id: UUIDType
    key: str
    value: str
    agent: str
    created_at: datetime | None = None


class EpisodeDigestItem(BaseModel):
    id: UUIDType
    agent: str
    summary: str | None
    created_at: datetime


class FactReviewAction(BaseModel):
    id: UUIDType
    action: Literal["confirm", "reject", "edit"]
    value: str | None = None


class FactReviewRequest(BaseModel):
    actions: list[FactReviewAction]


# ── REST: routing log ─────────────────────────────────────────────────────────


class RoutingLogEntry(BaseModel):
    id: UUIDType
    session_id: str
    prompt: str
    method: str
    primary_agent: str
    confidence: float | None
    score_gap: float | None
    is_compound: bool
    raw_scores: dict[str, float] | None
    created_at: str


class ErrorDetail(BaseModel):
    detail: str | list[dict[str, Any]]


# ── REST: web data screens ────────────────────────────────────────────────────


class GoalListItem(BaseModel):
    id: UUIDType
    title: str
    objective: str
    status: str
    created_at: datetime


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


class AgentCostBucket(BaseModel):
    usd: float
    tokens: int
    calls: int
    prompt_tokens: int
    completion_tokens: int


class DailyCostBucket(BaseModel):
    date: str
    usd: float
    calls: int


class CostAnomalyItem(BaseModel):
    agent: str
    run_cost_usd: float
    baseline_cost_usd: float
    multiplier: float
    session_id: str | None
    detected_at: str


class CostAnomaliesResponse(BaseModel):
    anomalies: list[CostAnomalyItem]
    period_days: int


class WebCostSummaryResponse(BaseModel):
    total_usd: float
    total_tokens: int
    total_calls: int
    by_agent: dict[str, AgentCostBucket]
    by_plugin: dict[str, AgentCostBucket]
    by_day: list[DailyCostBucket]
    period: str


# ── REST: data portability ────────────────────────────────────────────────────


class DataDomainItem(BaseModel):
    name: str
    importable: bool
    count: int | None
    size_bytes: int


class DataDomainsResponse(BaseModel):
    domains: list[DataDomainItem]
    schema_revisions: list[str]
    total_records: int
    total_size_bytes: int


class DeleteIntentResponse(BaseModel):
    confirmation_token: str
    expires_at: str


class DeleteRequest(BaseModel):
    confirmation_token: str


class ImportResponse(BaseModel):
    domains_imported: list[str]
    rows_imported: dict[str, int]


# ── REST: workflows ───────────────────────────────────────────────────────────


class BranchResponse(BaseModel):
    condition: str
    to: str


class StepResultResponse(BaseModel):
    step_index: int
    task: str
    output: str
    success: bool
    error: str | None
    duration_ms: int
    step_id: str
    branch_taken: str | None
    attempt_count: int = 1
    no_results: bool = False


class WorkflowStepResponse(BaseModel):
    task: str
    agent_hint: str | None
    verify: str | None
    id: str
    branches: list[BranchResponse]
    default_next: str | None
    on_failure: str = "fail"
    planned_writes: list[str] = []
    approved_writes: list[str] = []


class WorkflowResponse(BaseModel):
    id: UUIDType
    name: str
    description: str
    schedule: str | None
    enabled: bool
    last_run_at: str | None
    next_run_at: str | None
    created_at: str


class WorkflowDetailResponse(WorkflowResponse):
    steps: list[WorkflowStepResponse]


class ConfirmItemOut(BaseModel):
    item_id: str
    agent: str
    tool: str | None = None
    effect_phrase: str
    summary: str
    conflict: str | None = None
    editable_field: str | None = None
    proposed_text: str | None = None


class HeldWriteOut(BaseModel):
    request_id: str
    source: Literal["workflow", "goal"]
    source_name: str
    owner_ref: str
    items: list[ConfirmItemOut]
    status: Literal["open", "approved", "denied", "expired"]
    created_at: str | None = None
    expires_at: str | None = None


class HeldWriteListResponse(BaseModel):
    items: list[HeldWriteOut]


class HeldWriteDecisionIn(BaseModel):
    choice: Literal["approve", "deny"]
    edits: dict[str, str] = {}


class WorkflowExecutionResponse(BaseModel):
    id: UUIDType
    workflow_id: UUIDType | None
    status: str
    step_results: list[StepResultResponse]
    steps_snapshot: list[WorkflowStepResponse] = []
    error: str | None
    summary: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class TriggerWorkflowResponse(BaseModel):
    status: str
    workflow_id: UUIDType
    execution_id: UUIDType


class CancelWorkflowExecutionResponse(BaseModel):
    status: Literal["cancelled", "not_running"]
    execution_id: UUIDType
    message: str


class ActorContextResponse(BaseModel):
    source: Literal["agent", "api", "system"]
    session_id: str | None = None
    user_message_id: str | None = None


class WorkflowRevisionResponse(BaseModel):
    id: UUIDType
    workflow_id: UUIDType
    revision_number: int
    change_type: Literal["created", "edited"]
    steps_before: list[WorkflowStepResponse]
    steps_after: list[WorkflowStepResponse]
    summary: str
    actor_source: Literal["agent", "api", "system"]
    actor_session_id: str | None = None
    actor_user_message_id: str | None = None
    created_at: str


# ── REST: eval ────────────────────────────────────────────────────────────────


class EvalChatRequest(BaseModel):
    prompt: str
    session_id: str = "eval"
    force_agent: str | None = None


class EvalRoutingInfo(BaseModel):
    primary_agent: str
    confidence: float
    routing_method: str
    is_compound: bool
    score_gap: float
    raw_scores: dict[str, float]


class EvalToolCall(BaseModel):
    tool_name: str
    args: dict[str, Any]
    duration_ms: int
    success: bool
    error: str | None = None
    gate: str = "none"
    parked: bool = False


class EvalConfirmRequest(BaseModel):
    session_id: str = "eval"
    choice: Literal["approve", "deny"]
    edits: dict[str, str] = {}


class EvalChatResponse(BaseModel):
    session_id: str
    response: str | None
    agent_used: str | None
    routing: EvalRoutingInfo | None
    pending_confirmation: bool
    error: str | None
    tool_calls: list[EvalToolCall] = []
    tokens_used: int = 0


# ── WebSocket protocol — Server → Client (inbound frames) ─────────────────────


class OnboardingMeta(BaseModel):
    session_id: str
    completed: bool


class WsConfirmAction(BaseModel):
    label: str
    value: str
    style: Literal["primary", "secondary", "danger"] | None = None


class WsMessageFrame(BaseModel):
    type: Literal["message"]
    message: MessageSchema
    onboarding: OnboardingMeta | None = None


class WsEditFrame(BaseModel):
    type: Literal["edit"]
    id: str
    thread_id: str | None = None
    text: str | None = None
    components: list[dict[str, Any]] = []


class WsConfirmItem(BaseModel):
    item_id: str
    agent: str
    tool: str | None = None
    effect_phrase: str
    summary: str
    conflict: str | None = None
    editable_field: str | None = None
    proposed_text: str | None = None


class WsConfirmSource(BaseModel):
    kind: Literal["workflow", "goal"]
    name: str


class WsConfirmRequestFrame(BaseModel):
    type: Literal["confirm_request"]
    id: str
    thread_id: str | None = None
    kind: Literal["write", "budget", "held", "prompt"]
    round: int = 1
    title: str
    items: list[WsConfirmItem]
    source: WsConfirmSource | None = None
    expires_at: str | None = None
    actions: list[WsConfirmAction]


class WsConfirmCancelFrame(BaseModel):
    type: Literal["confirm_cancel"]
    id: str
    thread_id: str | None = None
    # "answered": the user approved or denied it (possibly on another client).
    reason: Literal["answered"] | None = None


class WsTypingFrame(BaseModel):
    type: Literal["typing"]
    thread_id: str | None = None
    text: str | None = None


class WsTokenFrame(BaseModel):
    type: Literal["token"]
    thread_id: str | None = None
    text: str


class WsErrorFrame(BaseModel):
    type: Literal["error"]
    thread_id: str | None = None
    detail: str
    code: (
        Literal["busy", "retry_unavailable", "retry_failed", "retry_partial"] | None
    ) = None
    message_id: str | None = None
    reason_code: str | None = None
    reason_text: str | None = None
    rolled_back: bool | None = None
    rollback: RollbackRecordResponse | None = None
    plan: list[UndoPlanEntryResponse] | None = None


class WsMessageSupersededFrame(BaseModel):
    type: Literal["message_superseded"]
    thread_id: str | None = None
    message_id: str
    replaced_by: str


class WsMessageRollbackFrame(BaseModel):
    type: Literal["message_rollback"]
    thread_id: str | None = None
    message_id: str
    rollback: RollbackRecordResponse


class WsRefreshFrame(BaseModel):
    type: Literal["refresh"]
    thread_id: str | None = None
    screen: str


class WsPongFrame(BaseModel):
    type: Literal["pong"]


class WsTraceUpdateFrame(BaseModel):
    type: Literal["trace_update"]
    thread_id: str
    message_id: str
    partial: bool = False
    agent: str
    routing_method: str
    confidence: float
    score_gap: float
    is_compound: bool
    subtasks: list[str]
    memory_chunks: list[MemoryChunkTraceResponse]
    tool_calls: list[ToolCallTraceResponse]
    total_duration_ms: int
    skills_used: list[SkillUsageTraceResponse] = []
    workspace: WorkspaceUsageTraceResponse | None = None
    procedure: ProcedureUsageTraceResponse | None = None
    conductor_hint: list[dict[str, str]] | None = None
    conductor_ledger: list[ConductorLedgerEntryResponse] = []
    judgments: list[JudgmentTraceResponse] = []
    sources: list[SourceTraceResponse] = []
    effects_known: bool = False
    write_confirmations: list[WriteConfirmationOutcomeResponse] = []
    rollback: RollbackTraceResponse | None = None


class WsNotificationFrame(BaseModel):
    type: Literal["notification"]
    id: str
    event_type: str
    source: str
    title: str
    body: str
    target_type: str | None
    target_id: str | None
    created_at: datetime
    read: bool = False
    push_class: str
    delivery: str


WsInboundFrame = Annotated[
    Union[
        WsMessageFrame,
        WsEditFrame,
        WsConfirmRequestFrame,
        WsConfirmCancelFrame,
        WsTypingFrame,
        WsTokenFrame,
        WsErrorFrame,
        WsMessageSupersededFrame,
        WsMessageRollbackFrame,
        WsRefreshFrame,
        WsPongFrame,
        WsTraceUpdateFrame,
        WsNotificationFrame,
    ],
    Field(discriminator="type"),
]


# ── WebSocket protocol — Client → Server (outbound frames) ────────────────────


class WsScreenContext(BaseModel):
    screen: str
    goal_id: str | None = None
    workflow_id: str | None = None
    execution_id: str | None = None
    workspace_placed: list["WsWorkspacePlaced"] | None = None


class WsWorkspacePlaced(BaseModel):
    path: str
    size: int


class WsSendMessageFrame(BaseModel):
    type: Literal["message"]
    text: str
    thread_id: str | None = None
    context: WsScreenContext | None = None


class WsAckFrame(BaseModel):
    type: Literal["ack"]
    ids: list[str]


class WsConfirmFrame(BaseModel):
    type: Literal["confirm"]
    id: str
    thread_id: str
    choice: Literal["approve", "deny"]
    edits: dict[str, str] = {}


class WsActionFrame(BaseModel):
    type: Literal["action"]
    payload: str
    thread_id: str | None = None


class WsCommandFrame(BaseModel):
    type: Literal["command"]
    thread_id: str | None = None
    name: Literal[
        "cancel",
        "costs",
        "status",
        "onboarding",
        "reset",
        "reset_preview",
    ]


class WsComponentSubmitFrame(BaseModel):
    type: Literal["component_submit"]
    step_id: str
    values: dict[str, Any]
    session_id: str | None = None
    thread_id: str | None = None


class WsRetryFrame(BaseModel):
    type: Literal["retry"]
    message_id: str
    thread_id: str
    confirmed_plan: list[str] | None = None


class WsPingFrame(BaseModel):
    type: Literal["ping"]


WsOutboundFrame = Annotated[
    Union[
        WsSendMessageFrame,
        WsAckFrame,
        WsConfirmFrame,
        WsActionFrame,
        WsCommandFrame,
        WsComponentSubmitFrame,
        WsRetryFrame,
        WsPingFrame,
    ],
    Field(discriminator="type"),
]


# ── REST: dream memory ─────────────────────────────────────────────────────────


class DreamJournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUIDType
    run_id: UUIDType
    summary: str
    episodes_processed: int
    insights_promoted: int
    procedures_extracted: int
    plan_risks_surfaced: int
    pending_review: int
    created_at: datetime


class DreamArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUIDType
    run_id: UUIDType
    artifact_type: str
    content: str
    source_episode_ids: list[UUIDType]
    source_fact_ids: list[UUIDType]
    support_count: int
    distinct_session_count: int
    temporal_spread_days: int
    user_asserted_source_count: int
    faithfulness_score: float | None
    novelty_score: float | None
    retrievable: bool | None
    critic_a_verdict: str | None
    critic_a_reason: str | None
    critic_b_verdict: str | None
    critic_b_reason: str | None
    status: str
    user_revised_content: str | None
    promoted_to: str | None
    promoted_id: UUIDType | None
    created_at: datetime
    reviewed_at: datetime | None


class DreamReviseRequest(BaseModel):
    content: str


class DreamRollbackResponse(BaseModel):
    rolled_back: int
    summaries_flagged: int


# ── REST: memory feed ─────────────────────────────────────────────────────────


class MemoryFeedItem(BaseModel):
    id: UUIDType
    type: Literal["fact", "episode"]
    key: str | None
    value: str | None
    confidence: float | None
    reviewed: bool | None
    contradicted: bool | None
    provenance: str | None
    summary: str | None
    prompt_snippet: str | None
    agent: str
    created_at: datetime


class MemoryFeedResponse(BaseModel):
    items: list[MemoryFeedItem]
    next_before: datetime | None
    total_facts: int | None = None
    total_episodes: int | None = None


class TimelineBoundsResponse(BaseModel):
    earliest: datetime | None
    latest: datetime


class MemoryActivityDay(BaseModel):
    date: str
    count: int
    fact_count: int
    episode_count: int


class MemoryActivityResponse(BaseModel):
    days: list[MemoryActivityDay]
    max_count: int


# ── REST: UI manifest ─────────────────────────────────────────────────────────


class UiContributionSchema(BaseModel):
    id: str
    plugin: str
    kind: Literal["nav", "settings_section"]
    label: str
    icon: str
    path: str | None = None
    page_operation_id: str | None = None
    settings_operation_id: str | None = None
    priority: int = 100
    show_in_mobile_nav: bool = True


class UiManifestResponse(BaseModel):
    nav: list[UiContributionSchema]
    settings_sections: list[UiContributionSchema]

    @classmethod
    def from_domain(cls, manifest) -> UiManifestResponse:
        def to_schema(item) -> UiContributionSchema:
            return UiContributionSchema(
                id=item.id,
                plugin=item.plugin,
                kind=item.kind,
                label=item.label,
                icon=item.icon,
                path=item.path,
                page_operation_id=item.page_operation_id,
                settings_operation_id=item.settings_operation_id,
                priority=item.priority,
                show_in_mobile_nav=item.show_in_mobile_nav,
            )

        return cls(
            nav=[to_schema(item) for item in manifest.nav],
            settings_sections=[to_schema(item) for item in manifest.settings_sections],
        )


# ── REST: activity heatmap ────────────────────────────────────────────────────


class AgentDayCount(BaseModel):
    agent: str
    count: int


class HeatmapDay(BaseModel):
    date: str
    total: int
    agents: list[AgentDayCount]


class ActivityHeatmapResponse(BaseModel):
    days: list[HeatmapDay]
    agents: list[str]
    start: str
    end: str


# ── REST: memory graph ────────────────────────────────────────────────────────


class GraphEntityNode(BaseModel):
    id: UUIDType
    entity_type: str
    canonical_name: str
    aliases: list[str]
    attrs: dict
    degree: int


class GraphEdge(BaseModel):
    id: UUIDType
    source_id: UUIDType
    target_id: UUIDType
    predicate: str
    confidence: float


class MemoryGraphResponse(BaseModel):
    nodes: list[GraphEntityNode]
    edges: list[GraphEdge]


class EntityDetailResponse(BaseModel):
    entity: GraphEntityNode
    facts: list[FactDigestItem]
    episodes: list[EpisodeDigestItem]
    neighbours: list[GraphEntityNode]
    neighbour_edges: list[GraphEdge]


# ── REST: notifications ──────────────────────────────────────────────────────


class NotificationItem(BaseModel):
    id: str
    event_type: str
    source: str
    title: str
    body: str
    target_type: str | None
    target_id: str | None
    created_at: datetime
    read: bool
    push_class: str
    delivery: str


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    next_cursor: str | None


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    marked: int


# ── REST: quiet hours (Phase 177) ─────────────────────────────────────────────

_QUIET_HOURS_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class QuietHoursResponse(BaseModel):
    enabled: bool
    start: str | None
    end: str | None
    timezone: str | None
    active_now: bool
    held_count: int
    max_discretionary_per_day: int


class QuietHoursUpdate(BaseModel):
    model_config = ConfigDict(validate_default=True)

    enabled: bool
    start: str | None = None
    end: str | None = None
    timezone: str | None = None

    @field_validator("start", "end")
    @classmethod
    def _validate_time(cls, value: str | None, info: ValidationInfo) -> str | None:
        enabled = bool(info.data.get("enabled"))
        if value is None:
            if enabled:
                raise ValueError("required when quiet hours are enabled")
            return None
        if not _QUIET_HOURS_TIME_RE.match(value):
            raise ValueError("must be HH:MM in 24-hour time")
        if info.field_name == "end" and enabled and info.data.get("start") == value:
            raise ValueError("start and end must differ")
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            if info.data.get("enabled"):
                raise ValueError("required when quiet hours are enabled")
            return None
        try:
            ZoneInfo(value)
        except Exception:
            raise ValueError("must be a valid IANA timezone") from None
        return value


# ── REST: open loops ──────────────────────────────────────────────────────────


class LoopListItem(BaseModel):
    id: UUIDType
    title: str
    state: str
    claim_kind: str
    provenance: str
    confidence: float
    drift_rationale: str | None
    goal_id: UUIDType | None
    reminder_id: UUIDType | None
    created_at: str | None
    updated_at: str | None
    promoted: bool
    source_inflows: list[str]


class LoopTransitionResponse(BaseModel):
    id: UUIDType
    state: str
    confidence: float


# ── REST: contribution collisions ───────────────────────────────────────────────


class ContributionRefSchema(BaseModel):
    domain_id: UUIDType
    producer_kind: str
    source_function: str
    claim_kind: str


class CollisionLogEntrySchema(BaseModel):
    id: UUIDType
    contribution_a: ContributionRefSchema
    contribution_b: ContributionRefSchema
    matched_entity_id: UUIDType | None
    matched_target_face: str
    conflict_summary: str
    created_at: str

    @classmethod
    def from_entry(cls, entry: Any) -> "CollisionLogEntrySchema":
        return cls(
            id=entry.id,
            contribution_a=ContributionRefSchema(
                domain_id=entry.contribution_a_domain_id,
                producer_kind=entry.contribution_a_producer_kind,
                source_function=entry.contribution_a_source_function.value,
                claim_kind=entry.contribution_a_claim_kind.value,
            ),
            contribution_b=ContributionRefSchema(
                domain_id=entry.contribution_b_domain_id,
                producer_kind=entry.contribution_b_producer_kind,
                source_function=entry.contribution_b_source_function.value,
                claim_kind=entry.contribution_b_claim_kind.value,
            ),
            matched_entity_id=entry.matched_entity_id,
            matched_target_face=entry.matched_target_face.value,
            conflict_summary=entry.conflict_summary,
            created_at=entry.created_at.isoformat() if entry.created_at else "",
        )


# ── REST: priority snapshot & override ──────────────────────────────────────────


SourceKindLiteral = Literal["loop", "goal", "hypothesis", "relationship"]


class PriorityOverrideSchema(BaseModel):
    id: UUIDType
    pinned: bool
    anchor_source_kind: SourceKindLiteral
    anchor_source_id: UUIDType
    relation: Literal["above", "below"]
    submitted_at: datetime


class PrioritySnapshotItem(BaseModel):
    source_kind: SourceKindLiteral
    source_id: UUIDType
    title: str
    displayed_rank: int
    computed_rank: int
    overridden_from_computed: bool
    override: PriorityOverrideSchema | None

    @classmethod
    def from_merged_item(cls, item: Any) -> "PrioritySnapshotItem":
        return cls(
            source_kind=item.source_kind,
            source_id=item.source_id,
            title=item.title,
            displayed_rank=item.displayed_rank,
            computed_rank=item.computed_rank,
            overridden_from_computed=item.overridden_from_computed,
            override=PriorityOverrideSchema(
                id=item.override.id,
                pinned=item.override.pinned,
                anchor_source_kind=item.override.anchor_source_kind,
                anchor_source_id=item.override.anchor_source_id,
                relation=item.override.relation,
                submitted_at=item.override.submitted_at,
            )
            if item.override is not None
            else None,
        )


class PrioritySnapshotResponse(BaseModel):
    items: list[PrioritySnapshotItem]
    sources_failed: list[SourceKindLiteral]


class PriorityOverrideRequestSchema(BaseModel):
    source_kind: SourceKindLiteral
    source_id: UUIDType
    anchor_source_kind: SourceKindLiteral
    anchor_source_id: UUIDType
    relation: Literal["above", "below"]
    pinned: bool = False


# ── REST: skills ──────────────────────────────────────────────────────────────


class SkillResponse(BaseModel):
    id: UUIDType
    name: str
    slug: str
    description: str
    source: Literal["bundled", "imported"]
    origin_url: str | None
    bundling_plugin: str | None
    status: Literal["pending_review", "active", "disabled", "rejected"]
    has_scripts: bool
    executable_approved: bool = False
    script_filenames: list[str] = []
    created_at: str | None
    approved_at: str | None
    last_checked_at: str | None
    last_check_error: str | None


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]


class SkillReferenceFileSummary(BaseModel):
    filename: str
    content_type: str


class SkillDetailResponse(SkillResponse):
    instructions: str
    allowed_tools: list[str] | None
    reference_files: list[SkillReferenceFileSummary]
    previous_version: dict[str, Any] | None = None


class SkillImportRequest(BaseModel):
    url: str


# ── REST: workspace ───────────────────────────────────────────────────────────


WorkspaceRunOriginLiteral = Literal["conversation", "user", "unattended"]
WorkspaceRunStatusLiteral = Literal[
    "succeeded", "failed", "timed_out", "cancelled", "refused", "in_progress"
]
# "in_progress" is never written to workspace_runs.status (which stays one of the
# five closed WorkspaceRunStatus values) — it is the REST/trace projection of a
# row with ended_at IS NULL (Phase 116, follow-through).


class WorkspaceStatusResponse(BaseModel):
    available: bool
    bytes_used: int
    bytes_ceiling: int
    busy: bool
    last_reset_at: str | None
    last_used_at: str | None


class WorkspaceFileItem(BaseModel):
    path: str
    size: int
    modified_at: str
    is_dir: bool


class WorkspaceFileListResponse(BaseModel):
    files: list[WorkspaceFileItem]


class WorkspaceUploadResponse(BaseModel):
    path: str
    requested_path: str
    size: int
    deduplicated: bool


class WorkspaceFileTouchResponse(BaseModel):
    path: str
    op: str


class WorkspaceRunResponse(BaseModel):
    id: str | None
    started_at: str | None
    ended_at: str | None
    command: str
    origin: WorkspaceRunOriginLiteral
    thread_id: str | None
    message_id: str | None
    skill_id: str | None
    skill_script_path: str | None
    status: WorkspaceRunStatusLiteral
    exit_code: int | None
    output_preview: str
    output_file_path: str | None
    files_touched: list[WorkspaceFileTouchResponse]
    error_summary: str | None
    follow_through_notified: bool = False


class WorkspaceRunListResponse(BaseModel):
    runs: list[WorkspaceRunResponse]


class ProcedureEvidenceRefResponse(BaseModel):
    kind: str
    id: UUIDType


class ProcedureCandidateResponse(BaseModel):
    id: UUIDType
    source_kind: str
    provenance: str
    name: str
    trigger: str
    preconditions: list[str]
    steps: list[str]
    success_criteria: list[str]
    limits: list[str]
    evidence_refs: list[ProcedureEvidenceRefResponse]
    learning_refs: list[UUIDType]
    status: str
    submitted_at: datetime | None
    resolved_at: datetime | None


class ProcedureVersionResponse(BaseModel):
    id: UUIDType
    procedure_id: UUIDType
    version_number: int
    name: str
    trigger: str
    preconditions: list[str]
    steps: list[str]
    success_criteria: list[str]
    limits: list[str]
    provenance: str
    status: str
    evidence_refs: list[ProcedureEvidenceRefResponse]
    learning_refs: list[UUIDType]


class ProcedureReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "needs_review", "withdraw"]
    reason: str


class ProcedureDisableRequest(BaseModel):
    reason: str = "disabled by user"


class ProcedureEditRequest(BaseModel):
    name: str
    trigger: str
    preconditions: list[str] = []
    steps: list[str]
    success_criteria: list[str]
    limits: list[str] = []
    reason: str = "edited by user"


class ProcedureLifecycleEventResponse(BaseModel):
    kind: str
    reason: str
    version_id: UUIDType | None = None


class ProcedureFeedbackResponse(BaseModel):
    outcome: str
    summary: str
    procedure_version_id: UUIDType


class ProcedureSummaryResponse(BaseModel):
    id: UUIDType
    name: str
    identity_status: str
    version_status: str
    version_number: int
    trigger: str
    current_version_id: UUIDType | None = None
    evidence_refs: list[ProcedureEvidenceRefResponse]


class ProcedureDetailResponse(BaseModel):
    id: UUIDType
    name: str
    identity_status: str
    current_version_id: UUIDType | None = None
    versions: list[ProcedureVersionResponse]
    events: list[ProcedureLifecycleEventResponse]
    outcomes: list[ProcedureFeedbackResponse]


class ProcedureAdmissionResultResponse(BaseModel):
    candidate: ProcedureCandidateResponse
    version: ProcedureVersionResponse | None = None
