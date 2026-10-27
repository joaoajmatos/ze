from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from ze_agents.db import DBPool
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.types import (
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
)


def loop_from_row(row) -> OpenLoop:
    return OpenLoop(
        id=row["id"],
        title=row["title"],
        state=LoopState(row["state"]),
        provenance=row["provenance"],
        confidence=row["confidence"],
        goal_id=row["goal_id"],
        reminder_id=row["reminder_id"],
        confidence_prior=row["confidence_prior"],
        confidence_changed_at=row["confidence_changed_at"],
        dismissed_evidence_fingerprint=row["dismissed_evidence_fingerprint"],
        drift_deadline=row["drift_deadline"],
        drift_rationale=row["drift_rationale"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        confirmed_at=row["confirmed_at"],
        closed_at=row["closed_at"],
    )


def source_from_row(row) -> LoopSource:
    kind, evidence_id = row["evidence_kind"], row["evidence_id"]
    return LoopSource(
        id=row["id"],
        loop_id=row["loop_id"],
        role=LoopSourceRole(row["role"]),
        key=SourceKey(row["inflow"], row["source_ref"]),
        evidence=EvidenceRef(kind=kind, id=evidence_id)
        if kind and evidence_id
        else None,
        same_concern=row["same_concern"],
        promoted=row["promoted"],
        model=row["model"],
        latency_ms=row["latency_ms"],
        created_at=row["created_at"],
    )


class LoopStore(Protocol):
    """Row reads and queries. Every write is a `LoopLifecycle` event."""

    async def get(self, loop_id: UUID) -> OpenLoop | None: ...

    async def list(
        self, states: list[str] | None = None, *, since: datetime | None = None
    ) -> list[OpenLoop]: ...

    async def list_by_evidence(
        self, evidence_type: str, evidence_id: UUID
    ) -> list[OpenLoop]: ...

    async def count_evidence_links(self, loop_id: UUID) -> int: ...

    async def list_evidence(self, loop_id: UUID) -> list[EvidenceRef]: ...

    async def list_drift_candidates(self) -> list[OpenLoop]: ...

    async def list_sources(self, loop_id: UUID) -> list[LoopSource]: ...

    async def list_sources_for(
        self, loop_ids: list[UUID]
    ) -> dict[UUID, list[LoopSource]]: ...


class PostgresLoopStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def get(self, loop_id: UUID) -> OpenLoop | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM open_loops WHERE id = $1", loop_id)
        return loop_from_row(row) if row else None

    async def list(
        self, states: list[str] | None = None, *, since: datetime | None = None
    ) -> list[OpenLoop]:
        clauses: list[str] = []
        params: list = []
        if states:
            params.append(states)
            clauses.append(f"state = ANY(${len(params)})")
        if since is not None:
            params.append(since)
            clauses.append(f"updated_at > ${len(params)}")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM open_loops{where} ORDER BY created_at DESC", *params
            )
        return [loop_from_row(r) for r in rows]

    async def list_by_evidence(
        self, evidence_type: str, evidence_id: UUID
    ) -> list[OpenLoop]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ol.*
                FROM open_loops ol
                JOIN memory_relationships mr
                  ON mr.source_id = ol.id
                WHERE mr.source_type = 'open_loop'
                  AND mr.predicate = 'derived_from'
                  AND mr.target_type = $1
                  AND mr.target_id = $2
                """,
                evidence_type,
                evidence_id,
            )
        return [loop_from_row(r) for r in rows]

    async def count_evidence_links(self, loop_id: UUID) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS n
                FROM memory_relationships
                WHERE source_id = $1 AND source_type = 'open_loop'
                  AND predicate = 'derived_from'
                """,
                loop_id,
            )
        return row["n"] if row else 0

    async def list_evidence(self, loop_id: UUID) -> list[EvidenceRef]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT target_type, target_id
                FROM memory_relationships
                WHERE source_id = $1 AND source_type = 'open_loop'
                  AND predicate = 'derived_from'
                """,
                loop_id,
            )
        return [EvidenceRef(kind=r["target_type"], id=r["target_id"]) for r in rows]

    async def list_drift_candidates(self) -> list[OpenLoop]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM open_loops
                WHERE state = 'active'
                  AND drift_deadline IS NOT NULL
                  AND drift_deadline <= now()
                ORDER BY drift_deadline ASC
                """
            )
        return [loop_from_row(r) for r in rows]

    async def list_sources(self, loop_id: UUID) -> list[LoopSource]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM open_loop_sources WHERE loop_id = $1"
                " ORDER BY created_at",
                loop_id,
            )
        return [source_from_row(r) for r in rows]

    async def list_sources_for(
        self, loop_ids: list[UUID]
    ) -> dict[UUID, list[LoopSource]]:
        if not loop_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM open_loop_sources WHERE loop_id = ANY($1)"
                " ORDER BY created_at",
                loop_ids,
            )
        grouped: dict[UUID, list[LoopSource]] = {}
        for row in rows:
            grouped.setdefault(row["loop_id"], []).append(source_from_row(row))
        return grouped
