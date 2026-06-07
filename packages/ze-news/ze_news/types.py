from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class Article:
    url: str
    source_key: str
    title: str
    summary: str
    published_at: datetime
    tags: list[str] = field(default_factory=list)


@dataclass
class SourceConfig:
    key: str
    type: str
    url: str
    tags: list[str] = field(default_factory=list)


@dataclass
class PersonalizationContext:
    interest_text: str
    exclusions: list[str] = field(default_factory=list)
    explore_ratio: float = 0.2
    fact_count: int = 0


@runtime_checkable
class GoalTitleProvider(Protocol):
    async def list_active_goal_titles(self) -> list[str]: ...
