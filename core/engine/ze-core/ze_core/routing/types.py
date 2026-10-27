from __future__ import annotations

from dataclasses import dataclass, field

from ze_agents.defaults import (
    MODEL_ROUTER_FALLBACK,
    ROUTING_GAP_THRESHOLD,
    ROUTING_THRESHOLD,
)
from ze_agents.judgment import Judgment


@dataclass
class SubTask:
    agent: str
    prompt: str
    model: str = ""
    # Routing label set by the fallback decomposer: this subtask changes something.
    # Read only by is_mixed_gather_act; it gates nothing.
    changes: bool = False


@dataclass
class RoutingEnvelope:
    primary_agent: str
    confidence: float
    score_gap: float
    routing_method: str  # "embedding" | "haiku" | "fallback" | "forced" (eval only) | "screen" (chat_about) | "open_query" | "preset" (fetch_context reroutes)
    is_compound: bool
    subtasks: list[SubTask]
    requires_synthesis: bool
    raw_scores: dict[str, float] = field(default_factory=dict)
    is_sequential: bool = False
    judgment: Judgment | None = None
    threshold: float = ROUTING_THRESHOLD
    gap_threshold: float = ROUTING_GAP_THRESHOLD


@dataclass
class RouterConfig:
    threshold: float = ROUTING_THRESHOLD
    gap_threshold: float = ROUTING_GAP_THRESHOLD
    fallback_model: str = MODEL_ROUTER_FALLBACK
