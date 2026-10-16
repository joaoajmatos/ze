from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_memory.errors import FactRestoreConflictError, StoreError
from ze_memory.retriever import PostgresMemoryStore
from ze_memory.types import Fact


class _Embedder:
    def encode_passage(self, text: str) -> list[float]:
        return [0.1, 0.2]

    encode_query = encode_passage


def _store(conn: AsyncMock) -> PostgresMemoryStore:
    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=cm)
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)
    store._pool = pool
    store._embedder = _Embedder()
    store._settings = MagicMock()
    store._graph_store = None
    return store


async def test_write_reports_displaced_ids(monkeypatch):
    displaced = uuid4()
    new_id = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[{"id": displaced}])
    conn.fetchrow = AsyncMock(return_value={"id": new_id})
    store = _store(conn)
    monkeypatch.setattr("ze_memory.retriever.nli_config", lambda s: {})
    fact = Fact(predicate="favourite_colour", value="blue")

    result = await store._write_fact_with_contradiction_check(fact)

    assert result == new_id
    assert fact.displaced_ids == [displaced]


async def test_write_reports_semantic_displaced_ids(monkeypatch):
    sem = uuid4()
    new_id = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value={"id": new_id})
    store = _store(conn)
    monkeypatch.setattr("ze_memory.retriever.nli_config", lambda s: {})

    async def fake_semantic(self, *a, **k):
        return [sem]

    monkeypatch.setattr(
        PostgresMemoryStore, "_apply_semantic_contradiction_check", fake_semantic
    )
    fact = Fact(predicate="p", value="v")
    await store._write_fact_with_contradiction_check(fact)
    assert fact.displaced_ids == [sem]


async def test_displaced_ids_default_empty():
    assert Fact(predicate="p", value="v").displaced_ids == []


async def test_retract_and_restore_swaps_flags():
    fact_id, restore = uuid4(), [uuid4(), uuid4()]
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [{"id": fact_id, "contradicted": False}],
            [{"id": r, "contradicted": True} for r in restore],
        ]
    )
    store = _store(conn)
    await store.retract_fact_and_restore(fact_id, restore)
    sql = [c.args[0] for c in conn.execute.await_args_list]
    assert len(sql) == 2
    assert "contradicted = true" in sql[0]
    assert "contradicted = false" in sql[1]


async def test_retract_and_restore_missing_fact_conflicts():
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[[], []])
    store = _store(conn)
    with pytest.raises(FactRestoreConflictError):
        await store.retract_fact_and_restore(uuid4(), [])
    conn.execute.assert_not_awaited()


async def test_retract_and_restore_already_contradicted_conflicts():
    fid = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[[{"id": fid, "contradicted": True}], []])
    store = _store(conn)
    with pytest.raises(FactRestoreConflictError):
        await store.retract_fact_and_restore(fid, [])
    conn.execute.assert_not_awaited()


async def test_retract_and_restore_restore_id_not_contradicted_conflicts():
    fid, r = uuid4(), uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [{"id": fid, "contradicted": False}],
            [{"id": r, "contradicted": False}],
        ]
    )
    store = _store(conn)
    with pytest.raises(FactRestoreConflictError):
        await store.retract_fact_and_restore(fid, [r])
    conn.execute.assert_not_awaited()


async def test_retract_and_restore_missing_restore_row_conflicts():
    fid = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[[{"id": fid, "contradicted": False}], []])
    store = _store(conn)
    with pytest.raises(FactRestoreConflictError):
        await store.retract_fact_and_restore(fid, [uuid4()])
    conn.execute.assert_not_awaited()


def test_conflict_error_is_store_error():
    assert issubclass(FactRestoreConflictError, StoreError)
