"""Conversion from ze-personal's `PersonSource` into the shared `Contribution` seam type."""

from __future__ import annotations

from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_sdk.contribution import Contribution, SourceFunction, TargetFace

from ze_personal.contacts.types import PersonSource


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
    )
