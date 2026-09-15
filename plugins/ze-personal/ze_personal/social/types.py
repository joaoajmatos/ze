"""Job-internal working types for co-occurrence inference (Phase 130).

Never persisted directly — `CoOccurrenceCandidate`/`CoOccurrenceEvidenceEvent`
exist only in memory during a `SocialCooccurrenceJob` run. The durable record
is the `ze_correlation.types.Hypothesis` (unconfirmed/uncorroborated) or the
`ze_memory.graph.types.Relationship` (once promoted).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

Predicate = Literal["WORKS_ON", "COLLABORATES_WITH"]
SourceType = Literal["conversation", "email", "calendar"]


@dataclass
class CoOccurrenceEvidenceEvent:
    """One communication event (thread, meeting) linking two entities."""

    source_type: SourceType
    is_reply_or_attendee: bool  # False = CC-only / no-reply mention (research-tier weight)
    event_id: str  # thread id or calendar event id — the "distinct event" unit
    occurred_at: datetime
    external_ref: str | None = None


@dataclass
class CoOccurrenceCandidate:
    """One (person, project-or-person) pair under consideration this run."""

    source_entity_id: UUID  # person
    target_entity_id: UUID  # project, or another person
    predicate: Predicate
    evidence_events: list[CoOccurrenceEvidenceEvent] = field(default_factory=list)
    existing_hypothesis_id: UUID | None = None
    existing_edge_exists: bool = False
