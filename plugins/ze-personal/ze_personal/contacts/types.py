from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from ze_agents.claims import ClaimKind, Provenance


SOURCE_WEIGHTS: dict[str, float] = {
    "manual": 1.0,
    "conversation": 1.0,
    "email": 0.7,
    "calendar": 0.6,
    "research": 0.2,
}

_SOURCE_TYPE_TO_PROVENANCE: dict[str, Provenance] = {
    "manual": Provenance.PROMPT_SUPPLIED,
    "conversation": Provenance.SYNTHESIZED,
    "email": Provenance.LIVE_SEARCH,
    "calendar": Provenance.LIVE_SEARCH,
    "research": Provenance.SYNTHESIZED,
}


@dataclass
class Person:
    name: str
    aliases: list[str] = field(default_factory=list)
    classification: str = "unknown"  # "personal" | "professional" | "unknown"
    classification_confidence: float = 0.0
    relationship_to_user: str = ""
    contact_info: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    confirmed: bool = False
    dismissed: bool = False
    confidence: float = 0.0  # max(source.weight) across all sources
    claim_kind: ClaimKind = ClaimKind.IDENTITY
    provenance: Provenance = Provenance.SYNTHESIZED
    id: UUID | None = None
    first_seen: datetime | None = None
    last_mentioned: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class PersonSource:
    person_id: UUID
    source_type: str  # "conversation" | "manual" | "email" | "calendar" | "research"
    weight: float
    claim_kind: ClaimKind = ClaimKind.IDENTITY
    provenance: Provenance = Provenance.SYNTHESIZED
    raw_context: str = ""
    id: UUID | None = None
    created_at: datetime | None = None


@dataclass
class PersonCandidate:
    """Intermediate type produced by extraction — not yet stored as a Person."""

    name: str
    inferred_classification: str = "unknown"
    inferred_relationship: str = ""
    raw_context: str = ""
    source_type: str = "research"


@dataclass
class PersonContext:
    people: list[Person] = field(default_factory=list)
    token_estimate: int = 0


@dataclass
class StaleFollowUpNudge:
    name: str
    days_ago: int


@dataclass
class ProjectProposal:
    """Typed output of any project-mention extraction step (extractors, consolidator, agents)."""

    name: str
    confidence: float = 0.5
    source_type: str = "conversation"
    raw_context: str = ""


@dataclass
class RelationshipEdgeProposal:
    """Typed output of a WORKS_ON/COLLABORATES_WITH edge mention.

    `person_name` is always the source (a person); `target_name` is a project
    name for WORKS_ON or another person's name for COLLABORATES_WITH.
    """

    predicate: str  # "WORKS_ON" | "COLLABORATES_WITH"
    person_name: str
    target_name: str
    confidence: float = 0.5
    source_type: str = "conversation"
    raw_context: str = ""


@dataclass
class ContactProposal:
    """Typed output of any contact extraction step (extractors, consolidator, agents)."""

    name: str
    classification: str = "unknown"  # "personal" | "professional" | "unknown"
    relationship: str = ""
    contact_info: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.5
    confirmed: bool = False
    source_type: str = "conversation"
    claim_kind: ClaimKind = ClaimKind.IDENTITY
    provenance: Provenance = Provenance.SYNTHESIZED
    raw_context: str = ""
