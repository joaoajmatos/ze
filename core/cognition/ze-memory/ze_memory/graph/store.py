"""Graph store protocol and Postgres implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from ze_agents.claims import Confidence, DecayProfile, decay
from ze_logging import get_logger

from ze_memory.graph.types import GraphExpansion, Relationship

log = get_logger(__name__)

# Maps target type string to the GraphExpansion bucket it populates.
_TYPE_BUCKET = {
    "fact": "fact_ids",
    "entity": "entity_ids",
    "episode": "episode_ids",
    "procedure": "procedure_ids",
    "signal": "signal_ids",
    "open_loop": "open_loop_ids",
}


@runtime_checkable
class GraphStore(Protocol):
    async def upsert_relationship(self, relationship: Relationship) -> UUID: ...
    async def list_relationships(
        self,
        source_ids: list[UUID],
        predicates: list[str] | None = None,
    ) -> list[Relationship]: ...
    async def expand(
        self,
        seed_ids: list[UUID],
        max_hops: int = 1,
        limit: int = 20,
    ) -> GraphExpansion: ...


class PostgresGraphStore:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def upsert_relationship(self, relationship: Relationship) -> UUID:
        """Insert or update a relationship. Returns the row id."""
        async with self._pool.acquire() as conn:
            last_contact = relationship.last_contact
            confidence_value = relationship.confidence.value
            if relationship.target_id is not None:
                row = await conn.fetchrow(
                    """
                    INSERT INTO memory_relationships
                      (source_id, source_type, predicate,
                       target_id, target_type, target_text,
                       confidence, provenance_id, creation_method, reviewed, last_contact)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, COALESCE($11, now()))
                    ON CONFLICT (source_id, predicate, target_id) WHERE target_id IS NOT NULL
                    DO UPDATE SET
                      confidence       = GREATEST(EXCLUDED.confidence, memory_relationships.confidence),
                      provenance_id    = COALESCE(EXCLUDED.provenance_id, memory_relationships.provenance_id),
                      last_contact     = GREATEST(EXCLUDED.last_contact, memory_relationships.last_contact),
                      updated_at       = now()
                    RETURNING id
                    """,
                    relationship.source_id,
                    relationship.source_type,
                    relationship.predicate,
                    relationship.target_id,
                    relationship.target_type,
                    relationship.target_text,
                    confidence_value,
                    relationship.provenance_id,
                    relationship.creation_method,
                    relationship.reviewed,
                    last_contact,
                )
            else:
                # Textual-only relationship — no unique constraint, always insert.
                row = await conn.fetchrow(
                    """
                    INSERT INTO memory_relationships
                      (source_id, source_type, predicate,
                       target_text, confidence, provenance_id, creation_method, last_contact)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, COALESCE($8, now()))
                    RETURNING id
                    """,
                    relationship.source_id,
                    relationship.source_type,
                    relationship.predicate,
                    relationship.target_text,
                    confidence_value,
                    relationship.provenance_id,
                    relationship.creation_method,
                    last_contact,
                )
        return row["id"]

    async def list_relationships(
        self,
        source_ids: list[UUID],
        predicates: list[str] | None = None,
    ) -> list[Relationship]:
        """Return all outbound relationships from the given source IDs."""
        if not source_ids:
            return []
        async with self._pool.acquire() as conn:
            if predicates:
                rows = await conn.fetch(
                    """
                    SELECT id, source_id, source_type, predicate,
                           target_id, target_type, target_text,
                           confidence, provenance_id, creation_method, reviewed,
                           created_at, updated_at, last_contact
                    FROM memory_relationships
                    WHERE source_id = ANY($1) AND predicate = ANY($2)
                    ORDER BY confidence DESC, updated_at DESC
                    """,
                    source_ids,
                    predicates,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, source_id, source_type, predicate,
                           target_id, target_type, target_text,
                           confidence, provenance_id, creation_method, reviewed,
                           created_at, updated_at, last_contact
                    FROM memory_relationships
                    WHERE source_id = ANY($1)
                    ORDER BY confidence DESC, updated_at DESC
                    """,
                    source_ids,
                )
        return [_rel_from_row(r) for r in rows]

    async def expand(
        self,
        seed_ids: list[UUID],
        max_hops: int = 1,
        limit: int = 20,
    ) -> GraphExpansion:
        """Bounded iterative expansion from seed_ids.

        Each hop fetches outbound relationships from the frontier, adds newly
        discovered target_ids to the next frontier. Stops at max_hops or when
        the cumulative relationship count reaches limit.
        """
        if not seed_ids:
            return GraphExpansion()

        expansion = GraphExpansion()
        visited: set[UUID] = set(seed_ids)
        frontier: list[UUID] = list(seed_ids)

        for _ in range(max_hops):
            if not frontier or len(expansion.relationships) >= limit:
                break

            remaining = limit - len(expansion.relationships)
            rels = await self.list_relationships(frontier)
            rels = rels[:remaining]

            next_frontier: list[UUID] = []
            for rel in rels:
                expansion.relationships.append(rel)
                if rel.target_id is not None and rel.target_id not in visited:
                    visited.add(rel.target_id)
                    next_frontier.append(rel.target_id)
                    # Bucket by target type.
                    bucket = _TYPE_BUCKET.get(rel.target_type or "")
                    if bucket == "fact_ids":
                        expansion.fact_ids.append(rel.target_id)
                    elif bucket == "entity_ids":
                        expansion.entity_ids.append(rel.target_id)
                    elif bucket == "episode_ids":
                        expansion.episode_ids.append(rel.target_id)
                    elif bucket == "procedure_ids":
                        expansion.procedure_ids.append(rel.target_id)
                    elif bucket == "signal_ids":
                        expansion.signal_ids.append(rel.target_id)
                    elif bucket == "open_loop_ids":
                        expansion.open_loop_ids.append(rel.target_id)

            frontier = next_frontier

        return expansion


def _hydrate_confidence(stored_value: float, last_contact: datetime | None) -> Confidence:
    """Read-time TIME_LINEAR decay from the persisted, undecayed base float."""
    if last_contact is None:
        return Confidence(value=stored_value, decay_profile=DecayProfile.TIME_LINEAR)
    now = datetime.now(timezone.utc)
    elapsed_days = (now - last_contact).total_seconds() / 86400
    decayed = decay(
        stored_value, DecayProfile.TIME_LINEAR, elapsed_days=max(elapsed_days, 0.0)
    )
    return Confidence(value=decayed, decay_profile=DecayProfile.TIME_LINEAR)


def _rel_from_row(row: Any) -> Relationship:
    return Relationship(
        id=row["id"],
        source_id=row["source_id"],
        source_type=row["source_type"],
        predicate=row["predicate"],
        target_id=row["target_id"],
        target_type=row["target_type"],
        target_text=row["target_text"],
        confidence=_hydrate_confidence(row["confidence"], row["last_contact"]),
        last_contact=row["last_contact"],
        provenance_id=row["provenance_id"],
        creation_method=row["creation_method"],
        reviewed=row["reviewed"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
