from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ze_agents.claims import ClaimKind

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
class EvidenceRef:
    evidence_type: str  # "fact" | "episode"
    evidence_id: UUID


@dataclass
class DriftingLoopMention:
    loop_id: UUID
    title: str
    mention_text: str
    evidence: list[EvidenceRef]
