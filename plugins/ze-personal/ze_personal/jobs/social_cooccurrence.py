"""Phase 130: forms and promotes person-project/person-person co-occurrence
inferences. See specs/phases/130-social-cognition-co-occurrence/."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from ze_logging import get_logger
from ze_sdk.proactive import proactive_job

from ze_agents.claims import ClaimKind, Provenance, Confidence, DecayProfile
from ze_correlation.types import EvidenceRef, Hypothesis
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace
from ze_plugin.contribution import EvidenceRef as ContributionEvidenceRef
from ze_sdk.contribution import submit_and_detect_collisions

from ze_personal.social.candidates import CoOccurrenceCandidateSource
from ze_personal.social.promotion import promote_hypothesis
from ze_personal.social.scoring import filter_fresh_evidence, is_corroborated, score_evidence
from ze_personal.social.types import CoOccurrenceCandidate, CoOccurrenceEvidenceEvent

log = get_logger(__name__)

UTC = timezone.utc


def _evidence_id(event_id: str) -> UUID:
    try:
        return UUID(event_id)
    except ValueError:
        # Test/fixture event ids aren't real UUIDs — derive a stable one so
        # evidence identity is still deterministic across runs.
        return uuid5(NAMESPACE_URL, event_id)


def _evidence_ref(event: CoOccurrenceEvidenceEvent) -> EvidenceRef:
    # `GraphCoOccurrenceCandidateSource` only ever emits "conversation" for
    # episode-sourced MENTIONS and "email"/"calendar" for signal-sourced ones
    # (candidates.py) — the mapping back to fact/episode/signal kind relies
    # on that invariant.
    kind = "episode" if event.source_type == "conversation" else "signal"
    return EvidenceRef(
        kind=kind,
        id=_evidence_id(event.event_id),
        label=f"{event.source_type} on {event.occurred_at.date().isoformat()}",
        external_ref=event.external_ref,
        origin=Provenance.LIVE_SEARCH
        if event.source_type in ("email", "calendar")
        else Provenance.SYNTHESIZED,
        retrieved_at=datetime.now(UTC),
        ingested_at=event.occurred_at,
    )


@proactive_job
class SocialCooccurrenceJob:
    job_id = "social_cooccurrence"

    def __init__(
        self,
        candidate_source: CoOccurrenceCandidateSource,
        hypothesis_store: Any,
        memory_store: Any,
        collision_store: Any = None,
        nli_client: Any = None,
    ) -> None:
        self._candidate_source = candidate_source
        self._hypothesis_store = hypothesis_store
        self._memory_store = memory_store
        self._collision_store = collision_store
        self._nli_client = nli_client

    async def run(self) -> None:
        candidates = await self._candidate_source.gather_candidates()
        for candidate in candidates:
            if candidate.existing_edge_exists:
                await self._reinforce_existing_edge(candidate)
                continue
            await self._process_inference_candidate(candidate)

    async def _reinforce_existing_edge(self, candidate: CoOccurrenceCandidate) -> None:
        """Edge Case (spec.md): if extraction already wrote WORKS_ON, inference
        MUST NOT duplicate the edge; it MAY reinforce `last_contact`."""
        graph_store = getattr(self._memory_store, "graph_store", None)
        if graph_store is None or not candidate.evidence_events:
            return
        from ze_memory.graph.types import Relationship

        latest = max(e.occurred_at for e in candidate.evidence_events)
        await graph_store.upsert_relationship(
            Relationship(
                source_id=candidate.source_entity_id,
                source_type="person",
                predicate=candidate.predicate,
                target_id=candidate.target_entity_id,
                target_type="project" if candidate.predicate == "WORKS_ON" else "person",
                confidence=Confidence(value=1.0, decay_profile=DecayProfile.TIME_LINEAR),
                last_contact=latest,
            )
        )

    async def _process_inference_candidate(self, candidate: CoOccurrenceCandidate) -> None:
        fresh = filter_fresh_evidence(candidate.evidence_events)
        if not fresh:
            return

        confidence = score_evidence(fresh)
        evidence_refs = [_evidence_ref(e) for e in fresh]

        existing = await self._find_existing_hypothesis(candidate)
        if existing is not None:
            if existing.promoted_at is not None:
                return
            await self._hypothesis_store.update_evidence(
                existing.id, evidence_refs, confidence
            )
            hypothesis = Hypothesis(
                id=existing.id,
                summary=existing.summary,
                narrative=existing.narrative,
                relation=existing.relation,
                confidence=confidence,
                relevance=existing.relevance,
                evidence=evidence_refs,
                entities=existing.entities,
                created_at=existing.created_at,
                claim_kind=existing.claim_kind,
                confirmed=existing.confirmed,
                promoted_at=existing.promoted_at,
            )
        else:
            hypothesis = await self._create_hypothesis(candidate, evidence_refs, confidence)

        if hypothesis.confirmed or is_corroborated(fresh):
            await promote_hypothesis(
                hypothesis,
                hypothesis_store=self._hypothesis_store,
                memory_store=self._memory_store,
                collision_store=self._collision_store,
                nli_client=self._nli_client,
            )

    async def _check_episode_exists(self, episode_id: UUID) -> bool:
        episodes = await self._memory_store.get_episodes_by_ids([episode_id])
        return len(episodes) > 0

    async def _check_signal_exists(self, signal_id: UUID) -> bool:
        signals = await self._memory_store.get_signals_by_ids([signal_id])
        return len(signals) > 0

    async def _find_existing_hypothesis(
        self, candidate: CoOccurrenceCandidate
    ) -> Hypothesis | None:
        pair = {candidate.source_entity_id, candidate.target_entity_id}
        hits = await self._hypothesis_store.list_by_entities(list(pair))
        for h in hits:
            if set(h.entities) == pair:
                return h
        return None

    async def _create_hypothesis(
        self,
        candidate: CoOccurrenceCandidate,
        evidence_refs: list[EvidenceRef],
        confidence: float,
    ) -> Hypothesis:
        verb = "works on" if candidate.predicate == "WORKS_ON" else "collaborates with"
        hypothesis = Hypothesis(
            id=uuid4(),
            summary=f"May {verb} — {len(evidence_refs)} recent evidence item(s)",
            narrative=(
                "Formed from recent communication co-occurrence; not yet "
                "corroborated or confirmed."
            ),
            relation="pattern",
            confidence=confidence,
            relevance=0.5,
            evidence=evidence_refs,
            entities=[candidate.source_entity_id, candidate.target_entity_id],
            created_at=datetime.now(UTC),
            claim_kind=ClaimKind.INFERENCE,
        )

        contribution = Contribution(
            claim_kind=ClaimKind.INFERENCE,
            provenance=Provenance.SYNTHESIZED,
            confidence=Confidence(value=confidence, decay_profile=DecayProfile.TIME_LINEAR),
            target_face=TargetFace.SELF,
            source_function=SourceFunction.REFLECTION,
            evidence=[
                ContributionEvidenceRef(kind=e.kind, id=e.id) for e in evidence_refs
            ],
            entity_ids=hypothesis.entities,
        )

        async def _write() -> UUID:
            await self._hypothesis_store.save(hypothesis)
            return hypothesis.id

        await submit_and_detect_collisions(
            contribution,
            write=_write,
            result_id=lambda rid: rid,
            producer_kind="social_cooccurrence_hypothesis",
            check_episode_exists=self._check_episode_exists,
            check_signal_exists=self._check_signal_exists,
            collision_store=self._collision_store,
            nli_client=self._nli_client,
        )
        log.info("cooccurrence_hypothesis_formed", hypothesis_id=str(hypothesis.id))
        return hypothesis
