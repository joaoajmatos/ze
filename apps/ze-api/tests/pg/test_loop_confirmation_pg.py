from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from ze_priority.turn import TurnSurfacing
from ze_priority.view import PriorityView
from ze_proactive.push_log_store import PushLogStore
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.review import confirm_loop
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import DECLARED_CONFIDENCE, LoopState

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

    await confirm_loop(store, loop.id)

    row = await store.get(loop.id)
    assert row.state is LoopState.ACTIVE
    assert row.confidence == pytest.approx(DECLARED_CONFIDENCE, abs=1e-6)
    assert row.provenance == "email"
    assert row.confirmed_at == row.updated_at
    expected = utcnow() + timedelta(days=7)
    assert abs((row.drift_deadline - expected).total_seconds()) < 60

    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET drift_deadline = now() - interval '1 day' WHERE id = $1",
            loop.id,
        )
    await DriftSweepJob(store).run()
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
        push_log=PushLogStore(pg_pool),
    )

    first = await surfacer.resume_loop_offers()
    assert {o.title for o in first} == {"Switch bank", "Dentist appointment"}
    async with pg_pool.acquire() as conn:
        rows = await conn.fetchval(
            "SELECT count(*) FROM push_log WHERE event_type LIKE 'worldstate_loop_offer:%'"
        )
    assert rows == 2

    assert await surfacer.resume_loop_offers() == []

    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE push_log SET sent_at = now() - interval '8 days'"
            " WHERE event_type LIKE 'worldstate_loop_offer:%'"
        )
    again = await surfacer.resume_loop_offers()
    assert {o.title for o in again} == {"Switch bank", "Dentist appointment"}
