from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def make_loop(
    pool: asyncpg.Pool,
    *,
    title: str = "Renew the passport",
    state: LoopState = LoopState.ACTIVE,
    provenance: str = LoopProvenance.USER_DECLARED,
    confidence: float = 0.9,
    deadline: datetime | None = None,
    confirmed_at: datetime | None = None,
    closed_at: datetime | None = None,
    rationale: str | None = None,
    fingerprint: str | None = None,
    reminder_id: UUID | None = None,
    goal_id: UUID | None = None,
    confidence_prior: float | None = None,
    created_at: datetime | None = None,
) -> OpenLoop:
    """Seed a row with plain SQL: a seed is not a lifecycle event."""
    if confirmed_at is None and state in (LoopState.ACTIVE, LoopState.DRIFTING):
        confirmed_at = utcnow()
    async with pool.acquire() as conn:
        loop_id = await conn.fetchval(
            """
            INSERT INTO open_loops
              (title, state, provenance, confidence, drift_deadline, confirmed_at,
               closed_at, drift_rationale, dismissed_evidence_fingerprint,
               reminder_id, goal_id, confidence_prior, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                    COALESCE($13, now()))
            RETURNING id
            """,
            title,
            state.value,
            provenance,
            confidence,
            deadline,
            confirmed_at,
            closed_at,
            rationale,
            fingerprint,
            reminder_id,
            goal_id,
            confidence_prior,
            created_at,
        )
    return await PostgresLoopStore(pool).get(loop_id)


async def fail_writes_to(pool: asyncpg.Pool, table: str) -> None:
    """Make every INSERT or UPDATE on `table` raise until the next reset (research R9)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO ze_test_faults (table_name) VALUES ($1) ON CONFLICT DO NOTHING",
            table,
        )


async def make_goal_with_gates(
    pool: asyncpg.Pool,
    *,
    title: str = "Ship the thing",
    status: str = "active",
    gates: list[tuple[str, datetime | None, bool]] = (),
) -> UUID:
    """gates: (status, fired_at, resolved) in after_sequence order, 1-based."""
    async with pool.acquire() as conn:
        goal_id = await conn.fetchval(
            """
            INSERT INTO goals (title, objective, success_condition, status)
            VALUES ($1, 'objective', 'done', $2) RETURNING id
            """,
            title,
            status,
        )
        for seq, (gate_status, fired_at, resolved) in enumerate(gates, start=1):
            await conn.execute(
                """
                INSERT INTO goal_gates
                  (goal_id, after_sequence, title, status, fired_at, resolved_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                goal_id,
                seq,
                f"Gate {seq}",
                gate_status,
                fired_at,
                fired_at + timedelta(hours=1) if resolved and fired_at else None,
            )
    return goal_id


async def make_episode(
    pool: asyncpg.Pool,
    *,
    agent: str = "companion",
    prompt: str = "I need to renew my passport",
    response: str = "Noted.",
    session_id: str = "pg-test",
) -> UUID:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO memory_episodes (session_id, agent, prompt, response)
            VALUES ($1, $2, $3, $4) RETURNING id
            """,
            session_id,
            agent,
            prompt,
            response,
        )


async def link_evidence(
    pool: asyncpg.Pool, loop_id: UUID, kind: str = "episode", evidence_id: UUID | None = None
) -> UUID:
    """Seed an evidence link with plain SQL; returns the evidence id."""
    from uuid import uuid4

    evidence_id = evidence_id or uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO memory_relationships
              (source_id, source_type, predicate, target_id, target_type,
               confidence, creation_method)
            VALUES ($1, 'open_loop', 'derived_from', $2, $3, 1.0, 'extracted')
            """,
            loop_id,
            evidence_id,
            kind,
        )
    return evidence_id


async def seed_source(
    pool: asyncpg.Pool,
    loop_id: UUID,
    inflow: str = "email",
    ref: str = "T1",
    *,
    role: str = "corroboration",
    promoted: bool = False,
) -> None:
    """Seed an open_loop_sources row with plain SQL."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO open_loop_sources"
            " (loop_id, role, inflow, source_ref, same_concern, promoted, model, latency_ms)"
            " VALUES ($1, $2, $3, $4, $5, $6, 'm', 100)",
            loop_id,
            role,
            inflow,
            ref,
            None if role == "origin" else 0.9,
            promoted,
        )
