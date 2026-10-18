from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from ze_api.api.shared_schemas import RollbackRecordResponse
from ze_api.api.v0.messages.schemas import (
    ConductorLedgerEntryResponse,
    JudgmentTraceResponse,
    CompactionTraceResponse,
    MemoryChunkTraceResponse,
    MessageSchema,
    ProcedureUsageTraceResponse,
    RollbackTraceResponse,
    SkillUsageTraceResponse,
    SourceTraceResponse,
    ScreenTraceResponse,
    TierTraceResponse,
    ToolCallTraceResponse,
    UndoPlanEntryResponse,
    WorkspaceUsageTraceResponse,
    WriteConfirmationOutcomeResponse,
)


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
    # Set on live frames whose components were just built; absent on replay and history.
    ui_version: str | None = None


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
    tier: TierTraceResponse | None = None
    screen: ScreenTraceResponse | None = None
    compaction: CompactionTraceResponse | None = None
    resume_recap_applied: bool = False


class WsUiActionResultFrame(BaseModel):
    type: Literal["ui_action_result"]
    id: str
    thread_id: str | None = None
    ok: bool
    line: str
    code: Literal["busy"] | None = None


class WsNotificationFrame(BaseModel):
    type: Literal["notification"]
    id: str
    event_type: str
    source: str
    title: str
    body: str
    target_type: str | None
    target_id: str | None
    target_parent_id: str | None
    created_at: datetime
    read: bool = False
    push_class: Literal["requested", "accountability", "discretionary"]
    urgency: Literal["low", "normal", "high"]
    delivery: Literal["delivered", "held", "released", "suppressed", "failed"]


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
        WsUiActionResultFrame,
    ],
    Field(discriminator="type"),
]


class WsScreenRef(BaseModel):
    kind: str = Field(max_length=64)
    id: str = Field(max_length=64)
    label: str | None = Field(None, max_length=120)
    component: str | None = Field(None, max_length=40)
    parent_id: str | None = Field(None, max_length=64)
    as_of: datetime | None = None


class WsCanvasRef(BaseModel):
    index: int
    type: str = Field(max_length=40)
    ref: WsScreenRef | None = None


class WsScreenContext(BaseModel):
    place: Literal["world", "ask", "doing", "mind", "governance", "plugin"] | None = (
        None
    )
    route: str | None = Field(None, max_length=200)
    origin: Literal["ask_bar", "chat_about", "preset"] | None = None
    # Caps (3 / 20 / 30 / 12) are applied by ScreenContext.from_wire; a schema limit would turn these into tuple types.
    subject: list[WsScreenRef] | None = None
    selection: list[WsScreenRef] | None = None
    visible: list[WsScreenRef] | None = None
    focused_module: str | None = Field(None, max_length=80)
    canvas: list[WsCanvasRef] | None = None
    captured_at: datetime | None = None
    workspace_placed: list["WsWorkspacePlaced"] | None = None
    compose: Literal["slipping", "decisions", "topic"] | None = None
    topic: str | None = Field(None, max_length=120)


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


class WsUiToolAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tool"]
    owner: str = Field(max_length=64)
    tool: str = Field(max_length=64)
    args: dict[str, str | int | float | bool] = {}


class WsUiActionFrame(BaseModel):
    type: Literal["ui_action"]
    id: str = Field(max_length=64)
    thread_id: str
    action: WsUiToolAction


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
        WsUiActionFrame,
        WsCommandFrame,
        WsComponentSubmitFrame,
        WsRetryFrame,
        WsPingFrame,
    ],
    Field(discriminator="type"),
]
