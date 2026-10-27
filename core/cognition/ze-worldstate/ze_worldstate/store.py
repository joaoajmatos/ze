from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef
from ze_agents.db import DBPool

from ze_worldstate.drift import DEFAULT_DRIFT_WINDOW_DAYS
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.types import (
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
)

log = get_logger(__name__)

# active -> drifting is only ever driven by drift.py/decay.py (Phase B automatic
# detection), never by this generic `transition()` call site used for user actions.
_ALLOWED_TRANSITIONS: dict[LoopState, set[LoopState]] = {
    LoopState.SUSPECTED: {LoopState.ACTIVE, LoopState.DROPPED},
    LoopState.ACTIVE: {LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED},
    LoopState.DRIFTING: {LoopState.CLOSED, LoopState.DROPPED},
    LoopState.CLOSED: set(),
    LoopState.DROPPED: set(),
}

# drifting -> active is a revive: only a user who explicitly asks to keep a loop
# in mind may bring one back (169). The REST confirm route, review.confirm_loop,
# decay and the drift sweep all keep rejecting it (they never pass user_asked).
_USER_ASKED_TRANSITIONS: dict[LoopState, set[LoopState]] = {
    LoopState.DRIFTING: {LoopState.ACTIVE},
}


# Postgres evaluates every SET expression against the old row, so the prior
# reads the value before this write. Only a real change stamps.
_CONFIDENCE_STAMP = (
    "confidence_prior = CASE WHEN confidence IS DISTINCT FROM {new} "
    "THEN confidence ELSE confidence_prior END, "
    "confidence_changed_at = CASE WHEN confidence IS DISTINCT FROM {new} "
    "THEN now() ELSE confidence_changed_at END, "
    "confidence = {new}"
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
    async def create(self, loop: OpenLoop) -> OpenLoop: ...

    async def get(self, loop_id: UUID) -> OpenLoop | None: ...

    async def list(
        self, states: list[str] | None = None, *, since: datetime | None = None
    ) -> list[OpenLoop]: ...

    async def transition(
        self, loop_id: UUID, new_state: str, *, user_asked: bool = False
    ) -> OpenLoop: ...

    async def resolve(
        self, loop_id: UUID, evidence: Sequence[EvidenceRef]
    ) -> OpenLoop | None: ...

    async def link(
        self,
        loop_id: UUID,
        *,
        reminder_id: UUID | None = None,
        goal_id: UUID | None = None,
    ) -> bool: ...

    async def link_entity(self, loop_id: UUID, entity_id: UUID) -> None: ...

    async def link_evidence(
        self, loop_id: UUID, evidence_type: str, evidence_id: UUID
    ) -> None: ...

    async def set_confidence(self, loop_id: UUID, confidence: float) -> None: ...

    async def set_dismissed_evidence_fingerprint(
        self, loop_id: UUID, fingerprint: str
    ) -> None: ...

    async def list_by_evidence(
        self, evidence_type: str, evidence_id: UUID
    ) -> list[OpenLoop]: ...

    async def count_evidence_links(self, loop_id: UUID) -> int: ...

    async def list_evidence(self, loop_id: UUID) -> list[EvidenceRef]: ...

    async def set_drift_deadline(self, loop_id: UUID, deadline: datetime) -> None: ...

    async def set_drift_rationale(self, loop_id: UUID, rationale: str) -> None: ...

    async def list_drift_candidates(self) -> list[OpenLoop]: ...

    async def record_corroboration(
        self, loop_id: UUID, *, window_days: int = DEFAULT_DRIFT_WINDOW_DAYS
    ) -> None: ...

    async def stamp_declared(
        self, loop_id: UUID, *, confidence: float, deadline: datetime
    ) -> None: ...

    async def add_source(self, source: LoopSource) -> LoopSource | None: ...

    async def list_sources(self, loop_id: UUID) -> list[LoopSource]: ...

    async def list_sources_for(
        self, loop_ids: list[UUID]
    ) -> dict[UUID, list[LoopSource]]: ...

    async def promote(
        self, loop_id: UUID, *, confidence: float, window_days: int
    ) -> OpenLoop | None: ...

    async def mark_source_promoted(self, source_id: UUID) -> None: ...


class PostgresLoopStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def create(self, loop: OpenLoop) -> OpenLoop:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO open_loops
                  (title, state, provenance, confidence, goal_id,
                   reminder_id, dismissed_evidence_fingerprint, confirmed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
                """,
                loop.title,
                loop.state.value,
                loop.provenance,
                loop.confidence,
                loop.goal_id,
                loop.reminder_id,
                loop.dismissed_evidence_fingerprint,
                loop.confirmed_at,
            )
        result = loop_from_row(row)
        log.info(
            "open_loop_created",
            loop_id=str(result.id),
            state=result.state.value,
            provenance=result.provenance,
        )
        return result

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

    async def transition(
        self, loop_id: UUID, new_state: str, *, user_asked: bool = False
    ) -> OpenLoop:
        target = LoopState(new_state)
        loop = await self.get(loop_id)
        if loop is None:
            raise LoopNotFoundError(f"Loop {loop_id} not found")

        allowed = set(_ALLOWED_TRANSITIONS.get(loop.state, set()))
        if user_asked:
            allowed |= _USER_ASKED_TRANSITIONS.get(loop.state, set())
        if target not in allowed:
            raise InvalidLoopTransitionError(
                f"Cannot transition loop {loop_id} from {loop.state.value} to {target.value}"
            )

        now = datetime.now(timezone.utc)
        confirmed_at = loop.confirmed_at
        closed_at = loop.closed_at
        if target == LoopState.ACTIVE:
            confirmed_at = now
        if target in (LoopState.CLOSED, LoopState.DROPPED):
            closed_at = now

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE open_loops
                SET state = $2, confirmed_at = $3, closed_at = $4, updated_at = now()
                WHERE id = $1 AND state = $5
                RETURNING *
                """,
                loop_id,
                target.value,
                confirmed_at,
                closed_at,
                loop.state.value,
            )
        if row is None:
            raise InvalidLoopTransitionError(
                f"Loop {loop_id} changed state before it could move to {target.value}"
            )
        result = loop_from_row(row)
        log.info(
            "open_loop_transitioned",
            loop_id=str(loop_id),
            from_state=loop.state.value,
            to_state=target.value,
        )
        return result

    async def resolve(
        self, loop_id: UUID, evidence: Sequence[EvidenceRef]
    ) -> OpenLoop | None:
        """Close a suspected, active or drifting loop on resolving evidence.

        The only edge into `closed` from `suspected`; `transition` still refuses it.
        Never stamps a dismissed-evidence fingerprint: the loop was done, not wrong.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    UPDATE open_loops
                    SET state = 'closed', closed_at = now(), updated_at = now()
                    WHERE id = $1 AND state IN ('suspected', 'active', 'drifting')
                    RETURNING *, (SELECT state FROM open_loops WHERE id = $1) AS prior_state
                    """,
                    loop_id,
                )
                if row is None:
                    exists = await conn.fetchval(
                        "SELECT 1 FROM open_loops WHERE id = $1", loop_id
                    )
                    if exists is None:
                        raise LoopNotFoundError(f"Loop {loop_id} not found")
                    return None
                for ref in evidence:
                    await conn.execute(
                        """
                        INSERT INTO memory_relationships
                          (source_id, source_type, predicate, target_id, target_type,
                           confidence, creation_method)
                        VALUES ($1, 'open_loop', 'derived_from', $2, $3, 1.0, 'extracted')
                        ON CONFLICT (source_id, predicate, target_id) WHERE target_id IS NOT NULL
                        DO NOTHING
                        """,
                        loop_id,
                        ref.id,
                        ref.kind,
                    )
        result = loop_from_row(row)
        log.info(
            "open_loop_transitioned",
            loop_id=str(loop_id),
            from_state=row["prior_state"],
            to_state=LoopState.CLOSED.value,
            via="resolve",
        )
        return result

    async def link_entity(self, loop_id: UUID, entity_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_relationships
                  (source_id, source_type, predicate, target_id, target_type,
                   confidence, creation_method)
                VALUES ($1, 'entity', 'has_open_loop', $2, 'open_loop', 1.0, 'extracted')
                ON CONFLICT (source_id, predicate, target_id) WHERE target_id IS NOT NULL
                DO NOTHING
                """,
                entity_id,
                loop_id,
            )

    async def link_evidence(
        self, loop_id: UUID, evidence_type: str, evidence_id: UUID
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_relationships
                  (source_id, source_type, predicate, target_id, target_type,
                   confidence, creation_method)
                VALUES ($1, 'open_loop', 'derived_from', $2, $3, 1.0, 'extracted')
                ON CONFLICT (source_id, predicate, target_id) WHERE target_id IS NOT NULL
                DO NOTHING
                """,
                loop_id,
                evidence_id,
                evidence_type,
            )
            await conn.execute(
                "UPDATE open_loops SET updated_at = now() WHERE id = $1", loop_id
            )

    async def set_confidence(self, loop_id: UUID, confidence: float) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE open_loops SET "
                + _CONFIDENCE_STAMP.format(new="$2")
                + ", updated_at = now() WHERE id = $1",
                loop_id,
                confidence,
            )

    async def set_dismissed_evidence_fingerprint(
        self, loop_id: UUID, fingerprint: str
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE open_loops SET dismissed_evidence_fingerprint = $2,"
                " updated_at = now() WHERE id = $1",
                loop_id,
                fingerprint,
            )

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

    async def link(
        self,
        loop_id: UUID,
        *,
        reminder_id: UUID | None = None,
        goal_id: UUID | None = None,
    ) -> bool:
        """Set the reminder or goal pointer once on a live loop; never overwrite."""
        if reminder_id is None and goal_id is None:
            return False
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE open_loops SET reminder_id = COALESCE(reminder_id, $2),"
                " goal_id = COALESCE(goal_id, $3), updated_at = now()"
                " WHERE id = $1 AND state IN ('suspected', 'active', 'drifting')"
                " AND (reminder_id IS DISTINCT FROM COALESCE(reminder_id, $2)"
                " OR goal_id IS DISTINCT FROM COALESCE(goal_id, $3))"
                " RETURNING id",
                loop_id,
                reminder_id,
                goal_id,
            )
        return row is not None

    async def set_drift_deadline(self, loop_id: UUID, deadline: datetime) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE open_loops SET drift_deadline = $2, updated_at = now()"
                " WHERE id = $1",
                loop_id,
                deadline,
            )

    async def stamp_declared(
        self, loop_id: UUID, *, confidence: float, deadline: datetime
    ) -> None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE open_loops SET "
                + _CONFIDENCE_STAMP.format(new="$2")
                + ", drift_deadline = $3,"
                " drift_rationale = NULL, confirmed_at = now(), updated_at = now()"
                " WHERE id = $1 RETURNING id",
                loop_id,
                confidence,
                deadline,
            )
        if row is None:
            raise LoopNotFoundError(f"Loop {loop_id} not found")

    async def set_drift_rationale(self, loop_id: UUID, rationale: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE open_loops SET drift_rationale = $2, updated_at = now()"
                " WHERE id = $1",
                loop_id,
                rationale,
            )

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

    async def record_corroboration(
        self, loop_id: UUID, *, window_days: int = DEFAULT_DRIFT_WINDOW_DAYS
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE open_loops
                SET drift_deadline = GREATEST(
                        COALESCE(drift_deadline, now()),
                        now() + make_interval(days => $2)),
                    updated_at = now()
                WHERE id = $1 AND state = 'active'
                """,
                loop_id,
                window_days,
            )

    async def add_source(self, source: LoopSource) -> LoopSource | None:
        evidence = source.evidence
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO open_loop_sources
                  (loop_id, role, inflow, source_ref, evidence_kind, evidence_id,
                   same_concern, promoted, model, latency_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (loop_id, inflow, source_ref) DO NOTHING
                RETURNING *
                """,
                source.loop_id,
                source.role.value,
                source.key.inflow,
                source.key.ref,
                evidence.kind if evidence else None,
                evidence.id if evidence else None,
                source.same_concern,
                source.promoted,
                source.model,
                source.latency_ms,
            )
        return source_from_row(row) if row else None

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

    async def promote(
        self, loop_id: UUID, *, confidence: float, window_days: int
    ) -> OpenLoop | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE open_loops
                SET state = 'active', {_CONFIDENCE_STAMP.format(new="GREATEST(confidence, $2)")},
                    confirmed_at = now(),
                    drift_deadline = now() + make_interval(days => $3),
                    drift_rationale = NULL, updated_at = now()
                WHERE id = $1 AND state = 'suspected'
                RETURNING *
                """,
                loop_id,
                confidence,
                window_days,
            )
        if row is None:
            return None
        log.info("open_loop_promoted", loop_id=str(loop_id))
        return loop_from_row(row)

    async def mark_source_promoted(self, source_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE open_loop_sources SET promoted = true WHERE id = $1",
                source_id,
            )
