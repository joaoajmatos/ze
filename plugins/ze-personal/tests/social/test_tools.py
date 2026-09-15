"""Tests for ze_personal.social.tools (Phase 130, User Stories 1-2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_correlation.types import EvidenceRef, Hypothesis
from ze_agents.claims import ClaimKind, Provenance
from ze_memory.types import Entity

from ze_personal.social.tools import confirm_project_membership, who_is_on_project

UTC = timezone.utc


def _project_entity(project_id):
    return Entity(id=project_id, entity_type="project", canonical_name="Launch")


def _person_entity(person_id, name="Alice"):
    return Entity(id=person_id, entity_type="person", canonical_name=name)


class TestWhoIsOnProjectHedged:
    async def test_unconfirmed_hypothesis_surfaces_as_hedged_not_confirmed(self):
        project_id, person_id = uuid4(), uuid4()
        memory_store = AsyncMock()
        memory_store.find_entity_by_name.return_value = _project_entity(project_id)
        memory_store.graph_store.list_relationships_by_target.return_value = []
        memory_store.get_entity.return_value = _person_entity(person_id)

        hypothesis = Hypothesis(
            id=uuid4(),
            summary="s",
            narrative="n",
            relation="pattern",
            confidence=0.5,
            relevance=0.5,
            evidence=[
                EvidenceRef(
                    kind="signal",
                    id=uuid4(),
                    label="email reply on Jan 3",
                    external_ref=None,
                    origin=Provenance.LIVE_SEARCH,
                    retrieved_at=datetime.now(UTC),
                )
            ],
            entities=[project_id, person_id],
            created_at=datetime.now(UTC),
            claim_kind=ClaimKind.INFERENCE,
        )
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = [hypothesis]

        result = await who_is_on_project(
            "Launch", memory_store=memory_store, hypothesis_store=hypothesis_store
        )

        assert result.success is True
        assert result.result["confirmed_members"] == []
        assert len(result.result["hedged_candidates"]) == 1
        assert result.result["hedged_candidates"][0]["person_name"] == "Alice"
        assert result.result["hedged_candidates"][0]["evidence_summaries"]

    async def test_promoted_hypothesis_excluded_from_hedged(self):
        project_id, person_id = uuid4(), uuid4()
        memory_store = AsyncMock()
        memory_store.find_entity_by_name.return_value = _project_entity(project_id)
        memory_store.graph_store.list_relationships_by_target.return_value = []

        promoted = Hypothesis(
            id=uuid4(),
            summary="s",
            narrative="n",
            relation="pattern",
            confidence=0.9,
            relevance=0.5,
            evidence=[],
            entities=[project_id, person_id],
            created_at=datetime.now(UTC),
            claim_kind=ClaimKind.INFERENCE,
            promoted_at=datetime.now(UTC),
        )
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = [promoted]

        result = await who_is_on_project(
            "Launch", memory_store=memory_store, hypothesis_store=hypothesis_store
        )

        assert result.result["hedged_candidates"] == []

    async def test_no_hypothesis_no_edge_returns_empty(self):
        project_id = uuid4()
        memory_store = AsyncMock()
        memory_store.find_entity_by_name.return_value = _project_entity(project_id)
        memory_store.graph_store.list_relationships_by_target.return_value = []
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = []

        result = await who_is_on_project(
            "Launch", memory_store=memory_store, hypothesis_store=hypothesis_store
        )

        assert result.result == {
            "project_name": "Launch",
            "confirmed_members": [],
            "hedged_candidates": [],
        }

    async def test_confirmed_member_within_window_is_listed(self):
        project_id, person_id = uuid4(), uuid4()
        memory_store = AsyncMock()
        memory_store.find_entity_by_name.return_value = _project_entity(project_id)
        edge = AsyncMock()
        edge.source_id = person_id
        edge.last_contact = datetime.now(UTC) - timedelta(days=2)
        memory_store.graph_store.list_relationships_by_target.return_value = [edge]
        memory_store.get_entity.return_value = _person_entity(person_id, "Bob")
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = []

        result = await who_is_on_project(
            "Launch", memory_store=memory_store, hypothesis_store=hypothesis_store
        )

        assert result.result["confirmed_members"] == ["Bob"]

    async def test_aged_out_confirmed_member_excluded(self):
        project_id, person_id = uuid4(), uuid4()
        memory_store = AsyncMock()
        memory_store.find_entity_by_name.return_value = _project_entity(project_id)
        edge = AsyncMock()
        edge.source_id = person_id
        edge.last_contact = datetime.now(UTC) - timedelta(days=45)
        memory_store.graph_store.list_relationships_by_target.return_value = [edge]
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = []

        result = await who_is_on_project(
            "Launch", memory_store=memory_store, hypothesis_store=hypothesis_store
        )

        assert result.result["confirmed_members"] == []


class TestConfirmProjectMembership:
    async def test_confirms_and_promotes(self):
        project_id, person_id = uuid4(), uuid4()
        hypothesis_id = uuid4()
        confirmed = Hypothesis(
            id=hypothesis_id,
            summary="s",
            narrative="n",
            relation="pattern",
            confidence=0.4,
            relevance=0.5,
            evidence=[],
            entities=[person_id, project_id],
            created_at=datetime.now(UTC),
            claim_kind=ClaimKind.INFERENCE,
            confirmed=True,
        )
        hypothesis_store = AsyncMock()
        hypothesis_store.confirm.return_value = confirmed
        memory_store = AsyncMock()
        memory_store.get_entity.return_value = _project_entity(project_id)
        memory_store.get_episodes_by_ids.return_value = []
        memory_store.get_signals_by_ids.return_value = []

        result = await confirm_project_membership(
            str(hypothesis_id),
            hypothesis_store=hypothesis_store,
            memory_store=memory_store,
        )

        assert result.success is True
        hypothesis_store.confirm.assert_awaited_once_with(hypothesis_id)
        memory_store.graph_store.upsert_relationship.assert_awaited_once()
        hypothesis_store.mark_promoted.assert_awaited_once_with(hypothesis_id)

    async def test_shares_promotion_path_with_job(self):
        """T024: confirm and the job must call the same promotion helper."""
        import ze_personal.social.tools as tools_module
        import ze_personal.jobs.social_cooccurrence as job_module

        assert tools_module.promote_hypothesis is job_module.promote_hypothesis
