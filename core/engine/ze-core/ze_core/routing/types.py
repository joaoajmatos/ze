from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ze_agents.defaults import (
    MODEL_ROUTER_FALLBACK,
    ROUTING_GAP_THRESHOLD,
    ROUTING_THRESHOLD,
)


@dataclass
class SubTask:
    agent: str
    intent: str
    prompt: str
    model: str = ""


@dataclass
class RoutingJudgment:
    """One attempted System One request, carried so embed_route can build trace rows."""

    result: Any  # ze_agents.system_one.SystemOneResult
    question_kinds: dict[str, str]
    consumed: frozenset[str] = frozenset()
    skip_reason: str | None = None


@dataclass
class RoutingEnvelope:
    primary_agent: str
    confidence: float
    score_gap: float
    routing_method: str  # "embedding" | "haiku" | "fallback"
    is_compound: bool
    subtasks: list[SubTask]
    requires_synthesis: bool
    raw_scores: dict[str, float] = field(default_factory=dict)
    is_sequential: bool = False
    complexity: str = "complex"  # "simple" | "complex"
    judgment: RoutingJudgment | None = None
    complexity_source: str = "regex"  # "regex" | "score"


@dataclass
class RouterConfig:
    threshold: float = ROUTING_THRESHOLD
    gap_threshold: float = ROUTING_GAP_THRESHOLD
    fallback_model: str = MODEL_ROUTER_FALLBACK
