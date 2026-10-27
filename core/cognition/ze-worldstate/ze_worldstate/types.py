from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ze_agents.claims import ClaimKind
from ze_agents.judgment import Judgment
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.decision import CommitDecision

LoopClaimKind = ClaimKind


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


_CLAIM_KIND_BY_STATE: dict[LoopState, LoopClaimKind | None] = {
    LoopState.SUSPECTED: LoopClaimKind.SUSPICION,
    LoopState.ACTIVE: LoopClaimKind.PRIORITY,
    LoopState.DRIFTING: LoopClaimKind.PRIORITY,
    LoopState.CLOSED: LoopClaimKind.PRIORITY,
    LoopState.DROPPED: None,
}


def loop_claim_kind(state: LoopState) -> LoopClaimKind | None:
    return _CLAIM_KIND_BY_STATE[state]


@dataclass
class OpenLoop:
    title: str
    provenance: str
    confidence: float
    state: LoopState = LoopState.SUSPECTED
    goal_id: UUID | None = None
    reminder_id: UUID | None = None
    confidence_prior: float | None = None
    confidence_changed_at: datetime | None = None
    dismissed_evidence_fingerprint: str | None = None
    drift_deadline: datetime | None = None
    drift_rationale: str | None = None
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    confirmed_at: datetime | None = None
    closed_at: datetime | None = None

    @property
    def claim_kind(self) -> LoopClaimKind | None:
        return loop_claim_kind(self.state)


@dataclass(frozen=True)
class SourceKey:
    inflow: str
    ref: str


class LoopSourceRole(StrEnum):
    ORIGIN = "origin"
    CORROBORATION = "corroboration"


@dataclass
class LoopSource:
    loop_id: UUID
    role: LoopSourceRole
    key: SourceKey
    evidence: EvidenceRef | None = None
    same_concern: float | None = None
    promoted: bool = False
    model: str | None = None
    latency_ms: int | None = None
    id: UUID | None = None
    created_at: datetime | None = None


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

    decision: CommitDecision
    judgment: Judgment | None = None
    source: SourceKey | None = None
    text: str = ""
    inflow: str = ""
