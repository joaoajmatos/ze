from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_personal.contacts.types import (
    ContactProposal,
    Person,
    PersonSource,
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
