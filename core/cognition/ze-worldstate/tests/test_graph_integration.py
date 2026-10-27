from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from ze_memory.graph.store import PostgresGraphStore


class _FakeConn:
    """A minimal in-memory stand-in for the subset of asyncpg used by
    PostgresGraphStore.list_relationships/expand, so US3's entity -> loop reachability
    (SC-004) can be exercised without a real DB. The `has_open_loop` row is seeded as
    the lifecycle's entity link writes it; the write itself is the lifecycle's pg test.
    """

    def __init__(self) -> None:
        self.relationships: list[dict] = []

    def link_entity(self, loop_id, entity_id) -> None:
        self.relationships.append(
            {
                "id": uuid4(),
                "source_id": entity_id,
                "source_type": "entity",
                "predicate": "has_open_loop",
                "target_id": loop_id,
                "target_type": "open_loop",
                "target_text": None,
                "confidence": 1.0,
                "provenance_id": None,
                "creation_method": "extracted",
                "reviewed": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "last_contact": datetime.now(timezone.utc),
            }
        )

    async def fetch(self, query: str, *args):
        if "FROM memory_relationships" in query:
            source_ids = args[0]
            return [r for r in self.relationships if r["source_id"] in source_ids]
        return []


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self._conn


async def test_loop_reachable_from_entity_neighbourhood():
    conn = _FakeConn()
    pool = _FakePool(conn)

    graph_store = PostgresGraphStore(pool)

    entity_id = uuid4()
    loop_id = uuid4()

    conn.link_entity(loop_id, entity_id)

    expansion = await graph_store.expand([entity_id])

    assert loop_id in expansion.open_loop_ids
