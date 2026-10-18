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

