from datetime import timedelta

import pytest

from tests.pg._builders import make_goal_with_gates, make_loop, utcnow

pytestmark = pytest.mark.pg


async def test_migrations_created_tables(pg_pool):
    async with pg_pool.acquire() as conn:
        for table in ("open_loops", "goal_gates", "memory_episodes", "memory_relationships", "push_log", "surfacing_memory"):
            assert await conn.fetchval("SELECT to_regclass($1)", table) is not None, table


async def test_reset_between_tests_first(pg_pool):
    await make_loop(pg_pool)
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM open_loops") == 1


async def test_reset_between_tests_second(pg_pool):
    await make_loop(pg_pool)
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM open_loops") == 1


async def test_goal_with_gates_round_trip(pg_pool):
    fired = utcnow() - timedelta(days=10)
    goal_id = await make_goal_with_gates(
        pg_pool,
        status="awaiting_gate",
        gates=[("approved", fired, True), ("awaiting_approval", fired, False), ("pending", None, False)],
    )
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT status, fired_at FROM goal_gates WHERE goal_id = $1 ORDER BY after_sequence", goal_id
        )
    assert [r["status"] for r in rows] == ["approved", "awaiting_approval", "pending"]
    assert rows[0]["fired_at"] == fired and rows[2]["fired_at"] is None
