from uuid import uuid4

from ze_agents.claims import ClaimKind, Provenance
from ze_personal.contacts.types import (
    ContactProposal,
    Person,
    PersonSource,
    _SOURCE_TYPE_TO_PROVENANCE,
)


def test_person_defaults_claim_kind_identity():
    person = Person(name="João Silva")
    assert person.claim_kind == ClaimKind.IDENTITY


def test_person_source_defaults_claim_kind_identity():
    source = PersonSource(person_id=uuid4(), source_type="conversation", weight=1.0)
    assert source.claim_kind == ClaimKind.IDENTITY


def test_contact_proposal_defaults_claim_kind_identity():
    proposal = ContactProposal(name="João Silva")
    assert proposal.claim_kind == ClaimKind.IDENTITY


def test_source_type_to_provenance_mapping():
    assert _SOURCE_TYPE_TO_PROVENANCE["manual"] == Provenance.PROMPT_SUPPLIED
    assert _SOURCE_TYPE_TO_PROVENANCE["conversation"] == Provenance.SYNTHESIZED
    assert _SOURCE_TYPE_TO_PROVENANCE["email"] == Provenance.LIVE_SEARCH
    assert _SOURCE_TYPE_TO_PROVENANCE["calendar"] == Provenance.LIVE_SEARCH
    assert _SOURCE_TYPE_TO_PROVENANCE["research"] == Provenance.SYNTHESIZED


def test_source_type_to_provenance_unrecognized_falls_back_to_synthesized():
    assert _SOURCE_TYPE_TO_PROVENANCE.get("unknown", Provenance.SYNTHESIZED) == (
        Provenance.SYNTHESIZED
    )
