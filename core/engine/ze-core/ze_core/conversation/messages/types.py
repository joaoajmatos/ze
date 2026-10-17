from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

MessageRole = Literal["user", "assistant"]
RollbackState = Literal[
    "partial",
    "rolled_back_awaiting_confirmation",
    "rolled_back_retry_failed",
    "superseded",
]
RollbackOutcome = Literal["undone", "failed", "not_attempted"]


def _pick(data: dict[str, Any], cls: type) -> dict[str, Any]:
    allowed = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in allowed}


@dataclass
class RollbackEntry:
    """One undo in a rollback. Timestamps and ids are strings: this is stored as JSONB."""

    entry_id: str
    call_index: int
    tool: str
    undo_tool: str
    effect_phrase: str
    outcome: RollbackOutcome
    at: str | None = None
    failure_code: str | None = None  # sanitized: error class or short tool error

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RollbackEntry:
        return cls(**_pick(data, cls))


@dataclass
class RollbackRecord:
    """What a Retry undid on a message; stored on `messages.rollback`."""

    state: RollbackState
    entries: list[RollbackEntry]
    started_at: str
    updated_at: str
    replaced_by: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RollbackRecord:
        values = _pick(data, cls)
        values["entries"] = [
            RollbackEntry.from_dict(e) for e in data.get("entries") or []
        ]
        return cls(**values)


@dataclass
class RollbackTrace:
    """Copy of the undone entries on the regenerated reply's trace."""

    replaces: str
    entries: list[RollbackEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RollbackTrace:
        return cls(
            replaces=data["replaces"],
            entries=[RollbackEntry.from_dict(e) for e in data.get("entries") or []],
        )


@dataclass
class Message:
    id: UUID
    role: MessageRole
    text: str | None
    components: list[dict[str, Any]]
    read: bool
    created_at: datetime
    thread_id: str | None
    replaces: UUID | None = None
    replaced_by: UUID | None = None
    rollback: RollbackRecord | None = None
    screen_context: dict[str, Any] | None = None


@dataclass
class MemoryChunkTrace:
    text: str
    score: (
        float  # retrieval relevance (real cosine similarity), not extraction confidence
    )
    source: str  # "fact" | "episode" | "profile"
    extraction_confidence: float | None = (
        None  # facts only — kept distinct from `score`
    )


@dataclass
class ToolCallTrace:
    name: str
    result_snippet: str  # first 200 chars of result
    duration_ms: int
    success: bool
    access: str = "unknown"  # "read" | "write" | "delegate" | "unknown"
    reversibility: str | None = None  # "reversible" | "irreversible" | None
    undo_tool: str | None = None
    gate: str = "none"  # "none" | "approved" | "denied" | "refused" | "expired"
    effect_phrase: str | None = None
    agent: str | None = None  # owning agent; nested delegate calls keep the delegate
    undo_args: dict[str, Any] | None = None  # ids and names only; never sent to clients
    undo_note: str | None = None
    call_index: int = 0  # position in the flattened call list


@dataclass
class CompactionTrace:
    span_start: int
    span_end: int


@dataclass
class SkillUsageTrace:
    skill_id: str
    name: str
    source: str  # "bundled" | "imported"
    trigger: str  # "automatic" | "explicit"
    similarity: float | None = None  # set only when trigger == "automatic"
    script_ran: bool = False
    below_floor: bool = False  # applied under match_threshold through a judgment


@dataclass
class WorkspaceUsageTrace:
    runs: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, str]] = field(default_factory=list)
    script_ran: bool = False
    unavailable: bool = False
    planned: list[str] | None = None


@dataclass
class ProcedureUsageTrace:
    invocation_id: str
    procedure_id: str
    version_id: str


@dataclass
class JudgmentTrace:
    question_id: str
    kind: str  # "noul" | "choice" | "score"
    latency_ms: int
    answer: str | float | None = None
    probabilities: dict[str, float] | None = None
    peakedness: float | None = None
    model: str | None = None
    input_tokens: int | None = None
    consumed: bool = False
    skip_reason: str | None = None


@dataclass
class TierTrace:
    agent: str
    tier: str  # "simple" | "full"
    decided_by: str
    model: str


@dataclass
class SourceTrace:
    url: str
    title: str = ""


@dataclass
class MessageTrace:
    agent: str
    routing_method: str  # "embedding" | "haiku" | "fallback"
    confidence: float
    score_gap: float
    is_compound: bool
    subtasks: list[str]
    memory_chunks: list[MemoryChunkTrace] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    total_duration_ms: int = 0
    compaction: CompactionTrace | None = None
    resume_recap_applied: bool = False
    loop_offer_ids: list[str] = field(default_factory=list)
    skills_used: list[SkillUsageTrace] = field(default_factory=list)
    workspace: WorkspaceUsageTrace | None = None
    procedure: ProcedureUsageTrace | None = None
    conductor_hint: list[dict[str, str]] | None = None
    conductor_ledger: list[dict[str, str]] = field(default_factory=list)
    judgments: list[JudgmentTrace] = field(default_factory=list)
    sources: list[SourceTrace] = field(default_factory=list)
    effects_known: bool = False  # True only when tool calls carry registry metadata
    # Phase 181: one row per confirmed item, every round (request_id, round, item_id,
    # agent, tool, effect, summary, outcome).
    write_confirmations: list[dict[str, Any]] = field(default_factory=list)
    rollback: RollbackTrace | None = None
    tier: TierTrace | None = None
