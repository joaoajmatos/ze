"""Tests for SocialCooccurrenceJob (Phase 130, User Stories 1-3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4


from ze_agents.claims import ClaimKind
from ze_correlation.types import Hypothesis
from ze_memory.graph.predicates import WORKS_ON
from ze_memory.types import Entity

from ze_personal.jobs.social_cooccurrence import SocialCooccurrenceJob
from ze_personal.social.types import CoOccurrenceCandidate, CoOccurrenceEvidenceEvent

UTC = timezone.utc


def _event(*, event_id="thread-1", days_ago=1, source_type="email", reply=True):
    return CoOccurrenceEvidenceEvent(
        source_type=source_type,
        is_reply_or_attendee=reply,
        event_id=event_id,
        occurred_at=datetime.now(UTC) - timedelta(days=days_ago),
    )


def _candidate(*, evidence_events=None, existing_edge_exists=False, predicate=WORKS_ON):
    return CoOccurrenceCandidate(
        source_entity_id=uuid4(),
        target_entity_id=uuid4(),
        predicate=predicate,
        evidence_events=evidence_events or [],
        existing_edge_exists=existing_edge_exists,
    )


def _make_job(candidate_source, hypothesis_store=None, memory_store=None):
    hypothesis_store = hypothesis_store or AsyncMock()
    memory_store = memory_store or AsyncMock()
    memory_store.get_episodes_by_ids.return_value = [object()]
    memory_store.get_signals_by_ids.return_value = [object()]
    return SocialCooccurrenceJob(
        candidate_source=candidate_source,
        hypothesis_store=hypothesis_store,
        memory_store=memory_store,
    )


class TestFormsHypothesisFromEvidence:
    async def test_creates_hypothesis_with_inference_claim_kind(self):
        candidate = _candidate(
            evidence_events=[_event(event_id="t1", days_ago=2)],
        )
        source = AsyncMock()
        source.gather_candidates.return_value = [candidate]
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = []
        memory_store = AsyncMock()

        job = _make_job(source, hypothesis_store, memory_store)
        await job.run()

        hypothesis_store.save.assert_awaited_once()
        saved: Hypothesis = hypothesis_store.save.await_args.args[0]
        assert saved.claim_kind == ClaimKind.INFERENCE
        assert set(saved.entities) == {
            candidate.source_entity_id,
            candidate.target_entity_id,
        }
        assert len(saved.evidence) == 1

    async def test_does_not_write_graph_edge_for_single_event(self):
        candidate = _candidate(evidence_events=[_event(event_id="t1", days_ago=2)])
        source = AsyncMock()
        source.gather_candidates.return_value = [candidate]
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = []
        memory_store = AsyncMock()

        job = _make_job(source, hypothesis_store, memory_store)
        await job.run()

        memory_store.graph_store.upsert_relationship.assert_not_awaited()
        hypothesis_store.mark_promoted.assert_not_awaited()

    async def test_stale_evidence_forms_no_hypothesis(self):
        candidate = _candidate(evidence_events=[_event(event_id="t1", days_ago=45)])
        source = AsyncMock()
        source.gather_candidates.return_value = [candidate]
        hypothesis_store = AsyncMock()

        job = _make_job(source, hypothesis_store)
        await job.run()

        hypothesis_store.save.assert_not_awaited()


class TestPromotesOnCorroboration:
    async def test_promotes_when_gate_passes(self):
        candidate = _candidate(
            evidence_events=[
                _event(event_id="t1", days_ago=10),
                _event(event_id="t2", days_ago=3),
            ]
        )
        source = AsyncMock()
        source.gather_candidates.return_value = [candidate]
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = []
        memory_store = AsyncMock()
        memory_store.get_entity.return_value = Entity(
            id=candidate.target_entity_id, entity_type="project", canonical_name="Launch"
        )

        job = _make_job(source, hypothesis_store, memory_store)
        await job.run()

        memory_store.graph_store.upsert_relationship.assert_awaited_once()
        hypothesis_store.mark_promoted.assert_awaited_once()

    async def test_does_not_promote_below_corroboration(self):
        candidate = _candidate(evidence_events=[_event(event_id="t1", days_ago=3)])
        source = AsyncMock()
        source.gather_candidates.return_value = [candidate]
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = []
        memory_store = AsyncMock()

        job = _make_job(source, hypothesis_store, memory_store)
        await job.run()

        hypothesis_store.save.assert_awaited_once()
        memory_store.graph_store.upsert_relationship.assert_not_awaited()
        hypothesis_store.mark_promoted.assert_not_awaited()

    async def test_second_run_does_not_repromote_already_promoted(self):
        source_id, target_id = uuid4(), uuid4()
        candidate = _candidate(
            evidence_events=[
                _event(event_id="t1", days_ago=10),
                _event(event_id="t2", days_ago=3),
            ]
        )
        candidate.source_entity_id = source_id
        candidate.target_entity_id = target_id

        already_promoted = Hypothesis(
            id=uuid4(),
            summary="s",
            narrative="n",
            relation="pattern",
            confidence=0.8,
            relevance=0.5,
            evidence=[],
            entities=[source_id, target_id],
            created_at=datetime.now(UTC),
            claim_kind=ClaimKind.INFERENCE,
            promoted_at=datetime.now(UTC),
        )
        source = AsyncMock()
        source.gather_candidates.return_value = [candidate]
        hypothesis_store = AsyncMock()
        hypothesis_store.list_by_entities.return_value = [already_promoted]
        memory_store = AsyncMock()

        job = _make_job(source, hypothesis_store, memory_store)
        await job.run()

        hypothesis_store.update_evidence.assert_not_awaited()
        hypothesis_store.mark_promoted.assert_not_awaited()
        memory_store.graph_store.upsert_relationship.assert_not_awaited()


class TestExistingEdgeReinforcedNotDuplicated:
    async def test_reinforces_last_contact_without_creating_hypothesis(self):
        candidate = _candidate(
            evidence_events=[_event(event_id="t1", days_ago=1)],
            existing_edge_exists=True,
        )
        source = AsyncMock()
        source.gather_candidates.return_value = [candidate]
        hypothesis_store = AsyncMock()
        memory_store = AsyncMock()

        job = _make_job(source, hypothesis_store, memory_store)
        await job.run()

        memory_store.graph_store.upsert_relationship.assert_awaited_once()
        hypothesis_store.save.assert_not_awaited()
        hypothesis_store.list_by_entities.assert_not_awaited()
