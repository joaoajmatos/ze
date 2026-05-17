from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID as UUIDType

from pydantic import BaseModel, ConfigDict, Field, RootModel


# ── WebSocket: client → server ────────────────────────────────────────────────

class UserMessage(BaseModel):
    type: Literal["message"]
    content: str


class ConfirmMessage(BaseModel):
    type: Literal["confirm"]
    decision: Literal["yes", "no", "edit"]
    edit_content: str | None = None


WsClientMessage = Annotated[
    UserMessage | ConfirmMessage,
    Field(discriminator="type"),
]


# ── WebSocket: server → client ────────────────────────────────────────────────

class TokenMessage(BaseModel):
    type: Literal["token"] = "token"
    content: str


class ConfirmationRequest(BaseModel):
    type: Literal["confirmation_request"] = "confirmation_request"
    draft: str
    agent: str
    action: str


class DoneMessage(BaseModel):
    type: Literal["done"] = "done"
    agent: str
    routing_method: str
    confidence: float | None


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str


class ConfirmationExpiredMessage(BaseModel):
    type: Literal["confirmation_expired"] = "confirmation_expired"


WsServerMessage = (
    TokenMessage
    | ConfirmationRequest
    | DoneMessage
    | ErrorMessage
    | ConfirmationExpiredMessage
)


# ── REST: capabilities ────────────────────────────────────────────────────────

CapabilityMode = Literal["autonomous", "confirm", "draft_only", "disabled"]


class CapabilityModeUpdate(BaseModel):
    mode: CapabilityMode


class AgentCapabilityConfig(BaseModel):
    """Per-agent entry from capabilities.yaml (enabled + intent modes)."""

    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None


class CapabilitiesResponse(RootModel[dict[str, AgentCapabilityConfig]]):
    """Full capabilities map keyed by agent name."""


class UpdateCapabilityResponse(RootModel[dict[str, AgentCapabilityConfig]]):
    """Updated capabilities for a single agent after PUT."""


# ── REST: memory ──────────────────────────────────────────────────────────────

class UserFactResponse(BaseModel):
    id: UUIDType
    key: str
    value: str
    agent: str
    confidence: float
    reviewed: bool
    contradicted: bool
    updated_at: datetime


class FactDigestItem(BaseModel):
    id: UUIDType
    key: str
    value: str
    agent: str


class EpisodeDigestItem(BaseModel):
    id: UUIDType
    agent: str
    summary: str | None
    created_at: datetime


class MemoryDigestResponse(BaseModel):
    unreviewed_facts: list[FactDigestItem]
    contradicted_facts: list[FactDigestItem]
    recent_episodes: list[EpisodeDigestItem]


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
