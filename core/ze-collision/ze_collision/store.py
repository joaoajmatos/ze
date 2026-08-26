from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from ze_agents.claims import ClaimKind
from ze_logging import get_logger
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_collision.types import CollisionLogEntry

log = get_logger(__name__)


class CollisionLogStore(Protocol):
    async def log(self, entry: CollisionLogEntry) -> CollisionLogEntry: ...

    async def list(
        self,
        *,
        entity_id: UUID | None = None,
        source_function: SourceFunction | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[CollisionLogEntry]: ...


def _row_to_entry(row: asyncpg.Record) -> CollisionLogEntry:
    return CollisionLogEntry(
        id=row["id"],
        contribution_a_domain_id=row["contribution_a_domain_id"],
        contribution_a_producer_kind=row["contribution_a_producer_kind"],
        contribution_a_source_function=SourceFunction(
            row["contribution_a_source_function"]
        ),
        contribution_a_claim_kind=ClaimKind(row["contribution_a_claim_kind"]),
        contribution_b_domain_id=row["contribution_b_domain_id"],
        contribution_b_producer_kind=row["contribution_b_producer_kind"],
        contribution_b_source_function=SourceFunction(
            row["contribution_b_source_function"]
        ),
        contribution_b_claim_kind=ClaimKind(row["contribution_b_claim_kind"]),
        matched_entity_id=row["matched_entity_id"],
        matched_target_face=TargetFace(row["matched_target_face"]),
        conflict_summary=row["conflict_summary"],
        created_at=row["created_at"],
    )


class PostgresCollisionLogStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def log(self, entry: CollisionLogEntry) -> CollisionLogEntry:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO contribution_collisions (
                    contribution_a_domain_id, contribution_a_producer_kind,
                    contribution_a_source_function, contribution_a_claim_kind,
                    contribution_b_domain_id, contribution_b_producer_kind,
                    contribution_b_source_function, contribution_b_claim_kind,
                    matched_entity_id, matched_target_face, conflict_summary
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
                """,
                entry.contribution_a_domain_id,
                entry.contribution_a_producer_kind,
                entry.contribution_a_source_function.value,
                entry.contribution_a_claim_kind.value,
                entry.contribution_b_domain_id,
                entry.contribution_b_producer_kind,
                entry.contribution_b_source_function.value,
                entry.contribution_b_claim_kind.value,
                entry.matched_entity_id,
                entry.matched_target_face.value,
                entry.conflict_summary,
            )
        log.info(
            "contribution_collision_logged",
            contribution_a_source_function=entry.contribution_a_source_function,
            contribution_b_source_function=entry.contribution_b_source_function,
            matched_entity_id=str(entry.matched_entity_id)
            if entry.matched_entity_id
            else None,
        )
        assert row is not None
        return _row_to_entry(row)

    async def list(
        self,
        *,
        entity_id: UUID | None = None,
        source_function: SourceFunction | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[CollisionLogEntry]:
        clauses: list[str] = []
        params: list[object] = []

        def _add(clause: str, value: object) -> None:
            params.append(value)
            clauses.append(clause.format(n=len(params)))

        if entity_id is not None:
            _add("matched_entity_id = ${n}", entity_id)
        if source_function is not None:
            _add(
                "(contribution_a_source_function = ${n}"
                " OR contribution_b_source_function = ${n})",
                source_function.value,
            )
        if since is not None:
            _add("created_at >= ${n}", since)
        if until is not None:
            _add("created_at <= ${n}", until)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        query = (
            f"SELECT * FROM contribution_collisions {where} "
            f"ORDER BY created_at DESC LIMIT ${len(params)}"
        )

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [_row_to_entry(row) for row in rows]
