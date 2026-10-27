import asyncpg
import pytest

from tests.pg._builders import fail_writes_to, make_loop
from ze_worldstate.types import LoopState

pytestmark = pytest.mark.pg


async def test_fault_trigger_raises_on_a_listed_table(pg_pool):
    loop = await make_loop(pg_pool, state=LoopState.SUSPECTED, confidence=0.3)
    await fail_writes_to(pg_pool, "open_loops")
    async with pg_pool.acquire() as conn:
        with pytest.raises(asyncpg.PostgresError, match="ze_test_fault"):
            await conn.execute(
                "UPDATE open_loops SET confidence = 0.5 WHERE id = $1", loop.id
            )
        with pytest.raises(asyncpg.PostgresError, match="ze_test_fault"):
            await conn.execute(
                "INSERT INTO open_loops (title, state, provenance, confidence)"
                " VALUES ('x', 'suspected', 'email', 0.3)"
            )
        await conn.execute(
            "INSERT INTO open_loop_sources (loop_id, role, inflow, source_ref)"
            " VALUES ($1, 'origin', 'email', 'm-1')",
            loop.id,
        )


async def test_fault_trigger_is_cleared_by_the_reset(pg_pool):
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM ze_test_faults") == 0
    loop = await make_loop(pg_pool)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET confidence = 0.8 WHERE id = $1", loop.id
        )
