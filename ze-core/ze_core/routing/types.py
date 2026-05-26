from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class SubTask:
    agent: str
    intent: str
    prompt: str
    model: str = ""


@dataclass
class RoutingEnvelope:
    primary_agent: str
    confidence: float
    score_gap: float
    routing_method: str        # "embedding" | "haiku" | "haiku_fallback"
    is_compound: bool
    subtasks: list[SubTask]
    requires_synthesis: bool
    raw_scores: dict[str, float] = field(default_factory=dict)
    is_sequential: bool = False
    complexity: str = "complex"  # "simple" | "complex"


@dataclass
class RouterConfig:
    threshold: float = 0.55
    gap_threshold: float = 0.10
    fallback_model: str = "anthropic/claude-haiku-4-5"


@runtime_checkable
class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[dict],
        model: str,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        **kwargs: Any,
    ) -> str: ...
