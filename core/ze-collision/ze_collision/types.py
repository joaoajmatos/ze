"""Types for cross-function contribution collision detection (Phase 126)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ze_agents.claims import ClaimKind
from ze_plugin.contribution import SourceFunction, TargetFace


@dataclass
class CollisionCandidate:
    """An in-memory record of a recently-submitted contribution, kept for the
    recency window used to find candidate pairs for a newly-submitted one.

    Not persisted — see `ze_collision.detect`'s module-level window.
    """

    domain_id: UUID
    producer_kind: str
    source_function: SourceFunction
    claim_kind: ClaimKind
    target_face: TargetFace
    # `None` means this contribution can never itself trigger or match a
    # comparison (NLI needs both sides' text) — it still enters the window as
    # a "past" candidate, per contracts/collisions-api.md's internal contract.
    content: str | None
    entity_ids: list[UUID]
    submitted_at: datetime


@dataclass
class CollisionLogEntry:
    """Append-only record of a detected cross-function contribution collision.

    Never itself a claim on the world-state — write-once, no update/delete path.
    """

    id: UUID | None
    contribution_a_domain_id: UUID
    contribution_a_producer_kind: str
    contribution_a_source_function: SourceFunction
    contribution_a_claim_kind: ClaimKind
    contribution_b_domain_id: UUID
    contribution_b_producer_kind: str
    contribution_b_source_function: SourceFunction
    contribution_b_claim_kind: ClaimKind
    matched_entity_id: UUID | None
    matched_target_face: TargetFace
    conflict_summary: str
    created_at: datetime | None
