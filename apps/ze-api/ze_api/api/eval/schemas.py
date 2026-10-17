from __future__ import annotations

from typing import Any, Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
)


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


class EvalChatRequest(BaseModel):
    prompt: str
    session_id: str = "eval"
    force_agent: str | None = None
    context: dict | None = None


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
    components: list[dict[str, Any]] = []
    tokens_used: int = 0


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
