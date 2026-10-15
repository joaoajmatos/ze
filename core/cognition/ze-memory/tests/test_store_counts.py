"""Tests for PostgresMemoryStore read counters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_memory.retriever import PostgresMemoryStore


class _async_ctx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


def _make_store(fetchrow_return) -> tuple[PostgresMemoryStore, AsyncMock]:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_async_ctx(conn))

    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    store._pool = pool
    return store, conn


async def test_count_unreviewed_facts_returns_count():
    store, conn = _make_store({"n": 7})

    assert await store.count_unreviewed_facts() == 7

    sql = conn.fetchrow.await_args.args[0]
    assert "memory_facts" in sql
    assert "reviewed = false" in sql
    assert "contradicted = false" in sql


async def test_count_unreviewed_facts_returns_zero():
    store, _ = _make_store({"n": 0})

    assert await store.count_unreviewed_facts() == 0
