from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ze_agents.claims import ClaimKind
from ze_agents.system_one import SystemOneResult
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.loop_judge import LoopGateDecision

LoopClaimKind = ClaimKind

# Confidence for a user-stated ("declared") loop, shared by the 168 explicit
# declaration path and the 169 user-asked track path.
DECLARED_CONFIDENCE = 0.9


class LoopProvenance:
    """Plain string-constant namespace, NOT an Enum — see FR-003 / research.md §3.

    Core-owned inflow values only; plugin-owned values (e.g. "email", "calendar")
    are supplied directly by the plugin, never declared here.
    """

    CONVERSATION = "conversation"
    INGESTION = "ingestion"
    USER_DECLARED = "user_declared"


class LoopState(StrEnum):
    SUSPECTED = "suspected"
    ACTIVE = "active"
    DRIFTING = "drifting"
    CLOSED = "closed"
    DROPPED = "dropped"


@dataclass
class OpenLoop:
    title: str
    claim_kind: LoopClaimKind
    provenance: str
    confidence: float
    state: LoopState = LoopState.SUSPECTED
    goal_id: UUID | None = None
    dismissed_evidence_fingerprint: str | None = None
    drift_deadline: datetime | None = None
    drift_rationale: str | None = None
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    confirmed_at: datetime | None = None
    closed_at: datetime | None = None


@dataclass
class DriftingLoopMention:
    loop_id: UUID
    title: str
    mention_text: str
    evidence: list[EvidenceRef]


class TrackOutcome:
    """Plain string constants for a `track_loop` ask (data-model.md)."""

    CREATED = "created"
    CONFIRMED = "confirmed"
    REINFORCED = "reinforced"
    REVIVED = "revived"


@dataclass
class TrackResult:
    ok: bool
    outcome: str | None = None
    loop: OpenLoop | None = None
    error: str | None = None


@dataclass
class TitleWriterResult:
    title: str
    implied_window_days: int | None = None


@dataclass
class LoopAdmission:
    """One loop-gate judgment. The node reads it by attribute; it never imports this type."""

    decision: LoopGateDecision
    judgment: SystemOneResult | None = None
    question_ids: tuple[str, ...] = ()
    question_kinds: dict[str, str] = field(default_factory=dict)
    consumed: frozenset[str] = frozenset()
    skip_reason: str | None = None
    commit: Callable[[], Awaitable[list[OpenLoop]]] | None = None
