from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.retriever import PostgresMemoryStore


def _store(rows: list) -> PostgresMemoryStore:
    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock()
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=cm)
    store._pool = pool
    store._embedder = None
    store._conn = conn
    return store


async def test_retract_matches_predicate_substring():
    fact_id = uuid4()
    store = _store(
        [
            {
                "id": fact_id,
                "predicate": "preference",
                "value": "dark mode",
                "embedding": None,
            }
        ]
    )
    ids = await store._retract_facts_matching("dark mode")
    assert ids == [fact_id]
    store._conn.execute.assert_awaited()


async def test_retract_returns_empty_when_nothing_matches():
    store = _store(
        [
            {
                "id": uuid4(),
                "predicate": "identity",
                "value": "lives in Lisbon",
                "embedding": None,
            }
        ]
    )
    ids = await store._retract_facts_matching("peanut allergy")
    assert ids == []
    store._conn.execute.assert_not_awaited()
