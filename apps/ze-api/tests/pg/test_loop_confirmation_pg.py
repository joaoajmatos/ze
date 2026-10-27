from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from ze_priority.surfacing_memory import PostgresSurfacingMemory
from ze_priority.turn import TurnSurfacing
from ze_priority.view import PriorityView
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.lifecycle import DeclaredStamp
from ze_worldstate.types import LoopState

from tests.pg._builders import make_loop, utcnow

pytestmark = pytest.mark.pg


async def test_confirm_stamps_the_row_and_feeds_the_drift_sweep(pg_pool):
    store = PostgresLoopStore(pg_pool)
    loop = await make_loop(
        pg_pool,
        state=LoopState.SUSPECTED,
        provenance="email",
        confidence=0.35,
        confirmed_at=None,
    )

    await LoopLifecycle(pg_pool).confirm(loop.id)

    row = await store.get(loop.id)
    assert row.state is LoopState.ACTIVE
    assert row.confidence == pytest.approx(DeclaredStamp.CONFIDENCE, abs=1e-6)
    assert row.provenance == "email"
    assert row.confirmed_at == row.updated_at
    expected = utcnow() + timedelta(days=7)
    assert abs((row.drift_deadline - expected).total_seconds()) < 60

    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET drift_deadline = now() - interval '1 day' WHERE id = $1",
            loop.id,
        )
    await DriftSweepJob(store, LoopLifecycle(pg_pool)).run()
    assert (await store.get(loop.id)).state is LoopState.DRIFTING


async def test_resume_offers_are_recorded_and_cool_down_for_a_week(pg_pool):
    store = PostgresLoopStore(pg_pool)
    for title in ("Switch bank", "Dentist appointment"):
        await make_loop(
            pg_pool,
            title=title,
            state=LoopState.SUSPECTED,
            confidence=0.35,
            confirmed_at=None,
        )
    surfacer = TurnSurfacing(
        priority_view=MagicMock(spec=PriorityView),
        graph_store=AsyncMock(),
        loop_store=store,
        embedder=MagicMock(),
        memory=PostgresSurfacingMemory(pg_pool),
    )

    first = await surfacer.resume_loop_offers()
    assert {o.title for o in first} == {"Switch bank", "Dentist appointment"}
    offered = [o.loop_id for o in first]
    async with pg_pool.acquire() as conn:
        rows = await conn.fetchval(
            "SELECT count(*) FROM surfacing_memory"
            " WHERE kind = 'offer' AND source_kind = 'loop' AND source_id = ANY($1)",
            offered,
        )
    assert rows == 2

    assert await surfacer.resume_loop_offers() == []

    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE surfacing_memory SET recorded_at = now() - interval '8 days'"
            " WHERE source_id = ANY($1)",
            offered,
        )
    again = await surfacer.resume_loop_offers()
    assert {o.title for o in again} == {"Switch bank", "Dentist appointment"}
