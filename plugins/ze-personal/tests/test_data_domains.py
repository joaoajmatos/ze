from unittest.mock import AsyncMock, MagicMock

from ze_personal.plugin import PersonalPlugin


def _domain(name: str):
    domains = PersonalPlugin.data_domains(PersonalPlugin.__new__(PersonalPlugin))
    return next(d for d in domains if d.name == name)


def _pool(conn: AsyncMock) -> MagicMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=ctx)
    return pool


async def test_memory_facts_domain_exports_memory_facts():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await _domain("memory.facts").export(_pool(conn))

    sql = conn.fetch.call_args_list[0][0][0]
    assert "memory_facts" in sql
    assert "user_facts" not in sql


async def test_memory_episodes_domain_exports_memory_episodes():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await _domain("memory.episodes").export(_pool(conn))

    sql = conn.fetch.call_args_list[0][0][0]
    assert "memory_episodes" in sql
    assert "FROM episodes" not in sql


async def test_memory_facts_import_after_entities_and_episodes():
    # memory_facts has FKs to memory_entities and memory_episodes, so it must be
    # imported after them (lower delete_order = deleted first, imported last).
    facts = _domain("memory.facts")
    assert facts.delete_order < _domain("memory.entities").delete_order
    assert facts.delete_order < _domain("memory.episodes").delete_order
