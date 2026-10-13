from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg
from ze_agents.claims import ClaimKind
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
) -> OpenLoop:
    """Create through the real store; the deadline is set through the real store method."""
    store = PostgresLoopStore(pool)
    if confirmed_at is None and state in (LoopState.ACTIVE, LoopState.DRIFTING):
        confirmed_at = utcnow()
    loop = await store.create(
        OpenLoop(
            title=title,
            claim_kind=ClaimKind.PRIORITY,
            provenance=provenance,
            confidence=confidence,
            state=state,
            confirmed_at=confirmed_at,
        )
    )
    if deadline is not None:
        await store.set_drift_deadline(loop.id, deadline)
        loop = await store.get(loop.id)
    return loop


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
