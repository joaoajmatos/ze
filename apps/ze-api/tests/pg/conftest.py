import asyncio
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
    "ze_test_faults",
)

_FAULT_TABLES = ("open_loops", "memory_relationships", "open_loop_sources")

_FAULT_SQL = """
CREATE TABLE IF NOT EXISTS ze_test_faults (table_name text PRIMARY KEY);
CREATE OR REPLACE FUNCTION ze_test_fault() RETURNS trigger AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM ze_test_faults WHERE table_name = TG_TABLE_NAME) THEN
        RAISE EXCEPTION 'ze_test_fault: write to % refused', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


async def _install_fault_trigger(url: str) -> None:
    """Test-only: a row in ze_test_faults makes writes to that table raise (research R9)."""
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(_FAULT_SQL)
        for table in _FAULT_TABLES:
            await conn.execute(
                f"DROP TRIGGER IF EXISTS ze_test_fault_{table} ON {table};"
                f"CREATE TRIGGER ze_test_fault_{table} BEFORE INSERT OR UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION ze_test_fault()"
            )
    finally:
        await conn.close()


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
    asyncio.run(_install_fault_trigger(url))
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
