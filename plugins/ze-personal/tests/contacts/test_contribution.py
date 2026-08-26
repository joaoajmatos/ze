from uuid import uuid4

from ze_agents.claims import ClaimKind, DecayProfile, Provenance
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_personal.contacts.contribution import person_source_to_contribution
from ze_personal.contacts.types import PersonSource


def test_person_source_to_contribution_round_trips():
    source = PersonSource(
        person_id=uuid4(),
        source_type="email",
        weight=0.7,
        provenance=Provenance.LIVE_SEARCH,
        raw_context="Ze extracted from email thread",
    )

    contribution = person_source_to_contribution(source)

    assert contribution.claim_kind == ClaimKind.IDENTITY
    assert contribution.provenance == Provenance.LIVE_SEARCH
    assert contribution.confidence.value == source.weight
    assert contribution.confidence.decay_profile == DecayProfile.EVIDENCE_WEIGHTED
    assert contribution.target_face == TargetFace.USER
    assert contribution.source_function == SourceFunction.SOCIAL_COGNITION
    assert contribution.evidence == []
