from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_memory.graph.predicates import WORKS_ON

from ze_personal.contacts.contribution import Contribution
from ze_personal.contacts.types import ContactProposal, Person
from ze_personal.graph.memory_hooks import (
    _write_contact_proposals,
    write_relationship_edge_via_seam,
)


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


def _make_memory_store():
    memory_store = AsyncMock()
    memory_store.get_episodes_by_ids.return_value = []
    memory_store.get_signals_by_ids.return_value = []
    return memory_store


async def test_write_relationship_edge_via_seam_writes_under_social_cognition():
    memory_store = _make_memory_store()

    await write_relationship_edge_via_seam(
        memory_store,
        source_id=uuid4(),
        target_id=uuid4(),
        target_type="project",
        predicate=WORKS_ON,
        confidence=0.8,
    )

    memory_store.graph_store.upsert_relationship.assert_awaited_once()
    rel = memory_store.graph_store.upsert_relationship.await_args.args[0]
    assert rel.predicate == WORKS_ON


async def test_write_relationship_edge_via_seam_rejects_wrong_source_function():
    """Regression test for research.md Decision 1: SOCIAL_COGNITION is
    licensed for IDENTITY only — a REFLECTION-tagged contribution routed
    through this seam call must never reach the graph write."""
    # Build the same Contribution shape `write_relationship_edge_via_seam`
    # constructs, but with the wrong source function, and assert the seam
    # itself (not our wrapper) is what rejects it.
    import pytest

    from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
    from ze_agents.errors import UnlicensedClaimKindError
    from ze_plugin.contribution import Contribution as SeamContribution
    from ze_plugin.contribution import SourceFunction, TargetFace, validate_and_submit

    bad_contribution = SeamContribution(
        claim_kind=ClaimKind.IDENTITY,
        provenance=Provenance.SYNTHESIZED,
        confidence=Confidence(value=0.8, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=TargetFace.USER,
        source_function=SourceFunction.REFLECTION,
    )

    write_called = False

    async def _write():
        nonlocal write_called
        write_called = True

    with pytest.raises(UnlicensedClaimKindError):
        await validate_and_submit(bad_contribution, _write)

    assert write_called is False
