from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from ze_api.api.shared_schemas import RollbackEntryResponse, RollbackRecordResponse


class UndoPlanEntryResponse(BaseModel):
    entry_id: str
    tool: str
    effect_phrase: str
    undo_note: str | None = None


class RollbackTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    replaces: str
    entries: list[RollbackEntryResponse] = []


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
        "parked",
        "denied",
        "refused",
        "refused_over_cap",
        "expired",
        "duplicate",
    ] = "none"
    effect_phrase: str | None = None
    agent: str | None = None
    call_index: int = 0
    call_id: str = ""
    start_offset_ms: int | None = None


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


class JudgmentBarResponse(BaseModel):
    name: str
    value: float


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
    surface: str | None = None
    bar: JudgmentBarResponse | None = None


class StageTimingResponse(BaseModel):
    name: str
    start_ms: int
    duration_ms: int
    run: int = 1


class ModelUsageResponse(BaseModel):
    model: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    max_prompt_tokens: int
    cost_usd: float
    estimated: bool = False


class TurnUsageResponse(BaseModel):
    main_model: str | None = None
    models: list[ModelUsageResponse] = []
    context_fill: float | None = None
    context_window: int | None = None
    estimated: bool = False
    system_one_tokens: int = 0


class RoutingScoreResponse(BaseModel):
    agent: str
    score: float


class RoutingThresholdsResponse(BaseModel):
    threshold: float
    gap: float


class CompactionTraceResponse(BaseModel):
    span_start: int
    span_end: int


class TierTraceResponse(BaseModel):
    agent: str
    tier: Literal["simple", "full"]
    decided_by: str
    model: str


class ScreenResolverTraceResponse(BaseModel):
    kind: str
    id: str
    status: Literal["ok", "missing", "changed", "failed", "timeout", "cut"]
    ms: int = 0


class ScreenTraceResponse(BaseModel):
    origin: Literal["ask_bar", "chat_about", "preset"] = "ask_bar"
    place: str | None = None
    route: str | None = None
    subject: list[str] = []
    selection_count: int = 0
    visible_count: int = 0
    canvas_count: int = 0
    focused_module: str | None = None
    captured_at: str | None = None
    note_chars: int = 0
    invalid: list[str] = []
    resolvers: list[ScreenResolverTraceResponse] = []


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
    tool_duration_ms: int
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
    tier: TierTraceResponse | None = None
    screen: ScreenTraceResponse | None = None
    turn_duration_ms: int | None = None
    paused_ms: int = 0
    stages: list[StageTimingResponse] = []
    usage: TurnUsageResponse | None = None
    routing_scores: list[RoutingScoreResponse] = []
    routing_thresholds: RoutingThresholdsResponse | None = None
    telemetry_partial: bool = False


class MessageTraceEntry(BaseModel):
    message_id: UUIDType
    trace: MessageTraceResponse


class MessageTracesResponse(BaseModel):
    traces: list[MessageTraceEntry]


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
