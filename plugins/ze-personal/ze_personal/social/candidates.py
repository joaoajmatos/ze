"""Where `SocialCooccurrenceJob` gets its (person, project-or-person) pairs
and their raw evidence from.

Kept as an explicit seam (`CoOccurrenceCandidateSource` Protocol) rather than
hardcoding a query in the job itself: the job's scoring/corroboration/
promotion logic (the part every acceptance scenario in spec.md actually
exercises) is independent of exactly how evidence is mined from the graph,
and the two are tested separately.

`GraphCoOccurrenceCandidateSource` is the default, built on the confirmed
shape of `memory_relationships`' `MENTIONS` edges (`ze_memory.retriever`'s
`_link_episode_entities`/`ingest_signal`: `source_type="episode"|"signal"`,
`predicate="MENTIONS"`, `target_type="entity"`) — two entities co-occur when
the same episode or signal mentions both. This recovers *that* a person and a
project were mentioned together, but not per-message reply-vs-CC-only
granularity: `MENTIONS` confidence is a flat per-source-type constant (0.8
episode / 0.9 signal), not a per-message signal. `is_reply_or_attendee`
therefore defaults to `True` here (treated as substantive contact, not
CC-only) — richer fidelity requires the originating inflow (ze-messenger,
ze-calendar) to attach that distinction somewhere queryable, a natural
follow-up integration and not a blocker for this phase's inference/promotion
pipeline itself.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from ze_memory.graph.predicates import COLLABORATES_WITH, WORKS_ON
from ze_memory.graph.store import GraphStore

from ze_personal.social.types import CoOccurrenceCandidate, CoOccurrenceEvidenceEvent


class CoOccurrenceCandidateSource(Protocol):
    async def gather_candidates(self) -> list[CoOccurrenceCandidate]: ...


_COOCCURRENCE_QUERY = """
    SELECT DISTINCT
      p.target_id AS person_id,
      other.target_id AS other_id,
      other_entity.entity_type AS other_type,
      p.source_id AS event_id,
      p.source_type AS event_source_type,
      GREATEST(p.updated_at, other.updated_at) AS occurred_at
    FROM memory_relationships p
    JOIN memory_relationships other
      ON other.source_id = p.source_id AND other.source_type = p.source_type
    JOIN memory_entities person_entity
      ON person_entity.id = p.target_id AND person_entity.entity_type = 'person'
    JOIN memory_entities other_entity
      ON other_entity.id = other.target_id
     AND other_entity.entity_type IN ('project', 'person')
    WHERE p.predicate = 'MENTIONS'
      AND other.predicate = 'MENTIONS'
      AND p.source_type IN ('episode', 'signal')
      AND p.target_id <> other.target_id
"""


class GraphCoOccurrenceCandidateSource:
    def __init__(self, pool: Any, graph_store: GraphStore) -> None:
        self._pool = pool
        self._graph_store = graph_store

    async def gather_candidates(self) -> list[CoOccurrenceCandidate]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_COOCCURRENCE_QUERY)

        candidates: dict[tuple[UUID, UUID], CoOccurrenceCandidate] = {}
        for row in rows:
            person_id: UUID = row["person_id"]
            other_id: UUID = row["other_id"]
            other_type: str = row["other_type"]
            predicate = WORKS_ON if other_type == "project" else COLLABORATES_WITH
            # Canonical pair key so (A, B) and (B, A) COLLABORATES_WITH mentions merge.
            key = (person_id, other_id) if person_id < other_id else (other_id, person_id)
            candidate = candidates.get(key)
            if candidate is None:
                candidate = CoOccurrenceCandidate(
                    source_entity_id=person_id,
                    target_entity_id=other_id,
                    predicate=predicate,
                )
                candidates[key] = candidate
            candidate.evidence_events.append(
                CoOccurrenceEvidenceEvent(
                    source_type="conversation"
                    if row["event_source_type"] == "episode"
                    else "email",
                    is_reply_or_attendee=True,
                    event_id=str(row["event_id"]),
                    occurred_at=row["occurred_at"],
                )
            )

        if not candidates:
            return []

        person_ids = list({c.source_entity_id for c in candidates.values()})
        existing_edges = await self._graph_store.list_relationships(
            person_ids, predicates=[WORKS_ON, COLLABORATES_WITH]
        )
        existing_pairs = {
            (e.source_id, e.target_id) for e in existing_edges if e.target_id
        }
        existing_pairs |= {(b, a) for a, b in existing_pairs}

        for candidate in candidates.values():
            pair = (candidate.source_entity_id, candidate.target_entity_id)
            candidate.existing_edge_exists = pair in existing_pairs

        return list(candidates.values())
