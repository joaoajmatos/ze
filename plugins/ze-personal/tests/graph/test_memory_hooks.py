from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_personal.contacts.contribution import Contribution
from ze_personal.contacts.types import ContactProposal, Person
from ze_personal.graph.memory_hooks import _write_contact_proposals


def _mistagged_contribution(source) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=source.provenance,
        confidence=Confidence(
            value=source.weight, decay_profile=DecayProfile.EVIDENCE_WEIGHTED
        ),
        target_face=TargetFace.USER,
        source_function=SourceFunction.SOCIAL_COGNITION,
        evidence=[],
    )


def make_person_store():
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=[])
    store.upsert = AsyncMock(
        return_value=Person(name="João Silva", id=uuid4(), confidence=0.8)
    )
    store.add_source = AsyncMock()
    return store


async def test_write_contact_proposals_rejects_mistagged_claim_kind():
    store = make_person_store()
    proposal = ContactProposal(name="João Silva", confidence=0.9)

    with patch(
        "ze_personal.graph.memory_hooks.person_source_to_contribution",
        side_effect=_mistagged_contribution,
    ):
        await _write_contact_proposals(store, [proposal], prompt="hi")

    store.upsert.assert_not_called()
    store.add_source.assert_not_called()


async def test_write_contact_proposals_persists_correctly_tagged_contribution():
    store = make_person_store()
    proposal = ContactProposal(name="João Silva", confidence=0.9)

    await _write_contact_proposals(store, [proposal], prompt="hi")

    store.upsert.assert_called_once()
    store.add_source.assert_called_once()
