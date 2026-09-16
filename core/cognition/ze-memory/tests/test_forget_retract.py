from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.retriever import PostgresMemoryStore


def _store(rows: list, embedder=None) -> PostgresMemoryStore:
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
    store._embedder = embedder
    store._conn = conn
    return store


def _row(fact_id, predicate: str, value: str, embedding=None) -> dict:
    return {
        "id": fact_id,
        "predicate": predicate,
        "value": value,
        "embedding": embedding,
    }


class _Embedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def encode(self, text: str) -> list[float]:
        return self._vectors[text]


async def test_retract_exact_identity_on_value():
    fact_id = uuid4()
    store = _store(
        [_row(fact_id, "preference", "dark mode")],
    )
    ids = await store._retract_facts_matching("dark mode")
    assert ids == [fact_id]
    store._conn.execute.assert_awaited()


async def test_retract_exact_identity_duplicate_rows():
    a = uuid4()
    b = uuid4()
    store = _store(
        [
            _row(a, "preference", "dark mode"),
            _row(b, "preference", "dark mode"),
        ]
    )
    ids = await store._retract_facts_matching("dark mode")
    assert set(ids) == {a, b}


async def test_retract_named_value_in_query():
    fact_id = uuid4()
    distractor = uuid4()
    store = _store(
        [
            _row(fact_id, "preference", "dark mode"),
            _row(distractor, "identity", "lives in Lisbon"),
        ]
    )
    ids = await store._retract_facts_matching("please forget that I prefer dark mode")
    assert ids == [fact_id]


async def test_retract_rejects_short_substring():
    dark = uuid4()
    air = uuid4()
    store = _store(
        [
            _row(dark, "preference", "dark mode"),
            _row(air, "preference", "airplane mode"),
        ]
    )
    ids = await store._retract_facts_matching("mode")
    assert ids == []
    store._conn.execute.assert_not_awaited()


async def test_retract_returns_empty_when_nothing_matches():
    store = _store(
        [_row(uuid4(), "identity", "lives in Lisbon")],
    )
    ids = await store._retract_facts_matching("peanut allergy")
    assert ids == []
    store._conn.execute.assert_not_awaited()


async def test_retract_blank_query_writes_nothing():
    store = _store([_row(uuid4(), "preference", "dark mode")])
    ids = await store._retract_facts_matching("   ")
    assert ids == []
    store._conn.fetch.assert_not_awaited()
    store._conn.execute.assert_not_awaited()


async def test_retract_rejects_cosine_075_top5_batch():
    a = uuid4()
    b = uuid4()
    query = "loose neighbor"
    embedder = _Embedder(
        {
            query: [1.0, 0.0],
        }
    )
    store = _store(
        [
            _row(a, "preference", "night theme", embedding=[0.76, 0.6499230724]),
            _row(b, "preference", "dim interface", embedding=[0.77, 0.6380423183]),
        ],
        embedder=embedder,
    )
    ids = await store._retract_facts_matching(query)
    assert ids == []
    store._conn.execute.assert_not_awaited()


async def test_retract_unique_high_cosine_single_hit():
    hit = uuid4()
    other = uuid4()
    query = "the night-time ui"
    embedder = _Embedder({query: [1.0, 0.0]})
    store = _store(
        [
            _row(hit, "preference", "dark mode", embedding=[0.90, 0.4358898944]),
            _row(other, "identity", "lives in Lisbon", embedding=[0.50, 0.8660254038]),
        ],
        embedder=embedder,
    )
    ids = await store._retract_facts_matching(query)
    assert ids == [hit]


async def test_retract_unique_embedding_skips_when_runner_up_too_close():
    a = uuid4()
    b = uuid4()
    query = "the night-time ui"
    embedder = _Embedder({query: [1.0, 0.0]})
    store = _store(
        [
            _row(a, "preference", "dark mode", embedding=[0.90, 0.4358898944]),
            _row(b, "preference", "night theme", embedding=[0.82, 0.5723635209]),
        ],
        embedder=embedder,
    )
    ids = await store._retract_facts_matching(query)
    assert ids == []
    store._conn.execute.assert_not_awaited()
