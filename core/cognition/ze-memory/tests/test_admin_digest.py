from unittest.mock import AsyncMock, MagicMock

from ze_memory.admin import get_memory_digest, list_facts


def _pool(conn: AsyncMock) -> MagicMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=ctx)
    return pool


async def test_list_facts_reads_memory_facts():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await list_facts(_pool(conn))

    sql = conn.fetch.call_args_list[0][0][0]
    assert "memory_facts" in sql
    assert "user_facts" not in sql
    assert "predicate AS key" in sql


async def test_get_memory_digest_reads_memory_tables():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await get_memory_digest(_pool(conn))

    sqls = [call[0][0] for call in conn.fetch.call_args_list]
    assert len(sqls) == 4
    assert all("user_facts" not in sql for sql in sqls)

    fact_sqls = [sql for sql in sqls if "memory_facts" in sql]
    episode_sqls = [sql for sql in sqls if "memory_episodes" in sql]
    assert len(fact_sqls) == 3
    assert len(episode_sqls) == 1
    assert all("predicate AS key" in sql for sql in fact_sqls)
