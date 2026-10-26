from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ze_proactive.types import OncePer


@dataclass(frozen=True)
class BarThresholds:
    """What a source asks of the push bar. `inline_cooldown_hours` is None for a
    source the conversation never mentions inline."""

    confidence: float
    relevance: float
    novelty_similarity_max: float
    grounding: float
    inline_cooldown_hours: float | None


@dataclass(frozen=True)
class PushCandidate:
    """One thing a source would push, built without reading anything slow.

    `relevance` and `evidence_labels` are thunks so the bar keeps its
    short-circuit: a candidate that fails on confidence costs no relevance
    build and no evidence read."""

    source_kind: str
    source_id: UUID
    entity: Any
    body: str
    claim: str
    confidence: float
    relevance: Callable[[], Awaitable[float]]
    evidence_labels: Callable[[], Awaitable[tuple[str, ...]]]
    once_per: OncePer
