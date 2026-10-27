from datetime import timedelta
from uuid import uuid4

import pytest
from ze_priority.surfacing_memory import PostgresSurfacingMemory

pytestmark = pytest.mark.pg


async def _age(pool, source_id, age: timedelta):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE surfacing_memory SET recorded_at = now() - $2::interval WHERE source_id = $1",
            source_id,
            age,
        )


async def test_record_then_recorded_within_reads_back_by_kind_and_id(pg_pool):
    memory = PostgresSurfacingMemory(pg_pool)
    a, b, other = uuid4(), uuid4(), uuid4()

    await memory.record("inline", "loop", [a, b])

    assert await memory.recorded_within("inline", "loop", a, 12)
    assert await memory.recorded_within("inline", "loop", b, 12)
    assert not await memory.recorded_within("offer", "loop", a, 12)
    assert not await memory.recorded_within("inline", "loop", other, 12)
    assert not await memory.recorded_within("inline", "goal", a, 12)


async def test_a_record_outside_the_window_is_not_recent(pg_pool):
    memory = PostgresSurfacingMemory(pg_pool)
    a = uuid4()
    await memory.record("inline", "loop", [a])

    await _age(pg_pool, a, timedelta(hours=13))

    assert not await memory.recorded_within("inline", "loop", a, 12)
    assert await memory.recorded_within("inline", "loop", a, 24)


async def test_record_deletes_rows_older_than_thirty_days(pg_pool):
    memory = PostgresSurfacingMemory(pg_pool)
    old, fresh = uuid4(), uuid4()
    await memory.record("offer", "loop", [old])
    await _age(pg_pool, old, timedelta(days=31))

    await memory.record("offer", "loop", [fresh])

    async with pg_pool.acquire() as conn:
        remaining = await conn.fetchval(
            "SELECT count(*) FROM surfacing_memory WHERE source_id = $1", old
        )
    assert remaining == 0
    assert await memory.recorded_within("offer", "loop", fresh, 1)


async def test_record_with_no_ids_writes_nothing(pg_pool):
    memory = PostgresSurfacingMemory(pg_pool)
    async with pg_pool.acquire() as conn:
        before = await conn.fetchval("SELECT count(*) FROM surfacing_memory")

    await memory.record("inline", "loop", [])

    async with pg_pool.acquire() as conn:
        after = await conn.fetchval("SELECT count(*) FROM surfacing_memory")
    assert after == before
