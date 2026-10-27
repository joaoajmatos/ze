import os

import asyncpg
import pytest
import pytest_asyncio

from tests.pg._container import start_container

RESET_TABLES = (
    "open_loops",
    "memory_relationships",
    "memory_episodes",
    "memory_facts",
    "memory_entities",
    "goals",
    "goal_gates",
    "goal_milestones",
    "push_log",
    "correlation_hypothesis",
    "priority_overrides",
    "notifications",
    "surfacing_memory",
    "workflow_executions",
    "workflows",
)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("ZE_TEST_PG") == "1":
        return
    skip = pytest.mark.skip(reason="set ZE_TEST_PG=1 (make test-pg) to run real-Postgres tests")
    for item in items:
        if "pg" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def pg_dsn():
    if os.environ.get("ZE_TEST_PG") != "1":
        pytest.skip("pg tests disabled")
    from ze_api.cli import migrate

    url = os.environ.get("ZE_TEST_PG_URL")
    handle = None
    if not url:
        handle = start_container()
        url = handle.asyncpg_url
    migrate.upgrade(url.replace("postgresql://", "postgresql+psycopg2://", 1))
    yield url
    if handle:
        handle.stop()


@pytest_asyncio.fixture
async def pg_pool(pg_dsn):
    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=4)
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE " + ", ".join(RESET_TABLES) + " RESTART IDENTITY CASCADE"
        )
    yield pool
    await pool.close()
