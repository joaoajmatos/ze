from datetime import timedelta

import pytest
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.types import LoopState

from tests.pg._builders import make_loop, utcnow

pytestmark = pytest.mark.pg


async def _aged(pool, title: str, state: LoopState, days: int):
    loop = await make_loop(pool, title=title, state=state)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET updated_at = $2 WHERE id = $1",
            loop.id,
            utcnow() - timedelta(days=days),
        )
    return loop


async def test_since_keeps_loops_updated_after_it(pg_pool):
    store = PostgresLoopStore(pg_pool)
    two = await _aged(pg_pool, "two days", LoopState.CLOSED, 2)
    five = await _aged(pg_pool, "five days", LoopState.DROPPED, 5)
    await _aged(pg_pool, "twenty days", LoopState.CLOSED, 20)
    await _aged(pg_pool, "still open", LoopState.ACTIVE, 1)

    rows = await store.list(["closed", "dropped"], since=utcnow() - timedelta(days=7))

    assert {r.id for r in rows} == {two.id, five.id}


async def test_without_since_every_closed_loop_returns(pg_pool):
    store = PostgresLoopStore(pg_pool)
    await _aged(pg_pool, "two days", LoopState.CLOSED, 2)
    await _aged(pg_pool, "twenty days", LoopState.CLOSED, 20)

    assert len(await store.list(["closed"])) == 2
