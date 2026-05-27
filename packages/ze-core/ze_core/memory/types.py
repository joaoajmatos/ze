from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class UserFact:
    key: str
    value: str
    agent: str = "global"
    confidence: float = 1.0
    reviewed: bool = False
    contradicted: bool = False
    id: UUID | None = None
    updated_at: datetime | None = None


@dataclass
class Episode:
    agent: str
    prompt: str
    response: str
    summary: str | None = None
    relevance: float = 0.0
    is_archive: bool = False
    id: UUID | None = None
    created_at: datetime | None = None
    # embedding is write-time only; kept None in context objects so AgentState
    # stays JSON-serialisable for the LangGraph checkpointer.
    embedding: Any = field(default=None, repr=False, compare=False)


@dataclass
class UserProfile:
    preferences: str
    habits: str
    topics: str
    relationships: str
    goals: str
    updated_at: datetime
    version: int


@dataclass
class MemoryContext:
    facts: list[UserFact] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    token_estimate: int = 0
    profile: UserProfile | None = None


@dataclass
class ConsolidationReport:
    facts_merged: int = 0
    facts_soft_expired: int = 0
    facts_hard_deleted: int = 0
    episodes_archived: int = 0
    episodes_deleted: int = 0
    profile_updated: bool = False
    duration_ms: int = 0
