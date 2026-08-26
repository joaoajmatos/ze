"""Conversion from ze-personal's `PersonSource` into the shared `Contribution` seam type."""

from __future__ import annotations

from uuid import UUID

from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_sdk.contribution import Contribution, SourceFunction, TargetFace

from ze_personal.contacts.types import PersonSource

# `person_id` placeholder sentinel before a new person's real id is known —
# matches consolidator.py's own `# placeholder, replaced below` convention.
_UNRESOLVED_PERSON_ID = UUID(int=0)


def person_source_to_contribution(source: PersonSource) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.IDENTITY,
        provenance=source.provenance,
        confidence=Confidence(
            value=source.weight,
            decay_profile=DecayProfile.EVIDENCE_WEIGHTED,
        ),
        target_face=TargetFace.USER,
        source_function=SourceFunction.SOCIAL_COGNITION,
        evidence=[],
        content=source.raw_context or None,
        entity_ids=[source.person_id]
        if source.person_id not in (None, _UNRESOLVED_PERSON_ID)
        else [],
    )
