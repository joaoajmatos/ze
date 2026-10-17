from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
)


class FactDigestItem(BaseModel):
    id: UUIDType
    key: str
    value: str
    agent: str
    created_at: datetime | None = None
    claim_kind: str | None = None
    confidence: float | None = None
    reviewed: bool | None = None
    contradicted: bool | None = None
    provenance: str | None = None


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


class MemoryFeedItem(BaseModel):
    id: UUIDType
    type: Literal["fact", "episode"]
    key: str | None
    value: str | None
    confidence: float | None
    reviewed: bool | None
    contradicted: bool | None
    provenance: str | None
    claim_kind: str | None = None
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
    neighbour_total: int
    neighbour_edges: list[GraphEdge]
