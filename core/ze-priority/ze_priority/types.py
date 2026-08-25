from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from ze_agents.claims import ClaimKind, Confidence
from ze_automation.goals.types import StuckGoal
from ze_correlation.types import Hypothesis
from ze_worldstate.types import LoopState, OpenLoop

SourceKind = Literal["loop", "goal", "hypothesis"]


@dataclass
class LoopSignal:
    state: LoopState
    confidence: float
    drift_deadline: datetime | None


@dataclass
class GoalSignal:
    kind: Literal["active", "awaiting_gate"]
    idle_days: int


@dataclass
class HypothesisSignal:
    confidence: float
    relevance: float


SourceSignal = LoopSignal | GoalSignal | HypothesisSignal


@dataclass
class PriorityItem:
    """The per-item row of a PriorityView ranking. Not persisted."""

    source_kind: SourceKind
    claim_kind: ClaimKind
    source_id: UUID
    title: str
    signal: SourceSignal
    priority: Confidence
    rank: int
    activity_at: datetime


@dataclass
class PriorityRanking:
    items: list[PriorityItem]
    sources_succeeded: set[SourceKind]
    sources_failed: set[SourceKind]
    generated_at: datetime


@dataclass
class PriorityCandidateRef:
    """An already-fetched source entity, scoped for `PriorityView.rank_subset()`.

    Carries the raw entity itself (not just an id) so `rank_subset` never needs
    to re-query a store — the caller (e.g. `AttentionArbitrationJob`) has already
    pulled its own eligibility-filtered subset.
    """

    source_kind: SourceKind
    entity: OpenLoop | StuckGoal | Hypothesis
