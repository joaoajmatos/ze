"""Tests for PostgresMemoryStore write paths: propose_events, propose_procedure, upsert_entity."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ze_memory.retriever import PostgresMemoryStore
from ze_memory.types import Entity, Event, Procedure


def _make_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = MagicMock(return_value=_async_ctx(conn))
    return pool, conn


class _async_ctx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


def _make_store(pool=None) -> tuple[PostgresMemoryStore, AsyncMock]:
    if pool is None:
        pool, conn = _make_pool()
    else:
        conn = pool.acquire.return_value._conn
    store = PostgresMemoryStore.__new__(PostgresMemoryStore)
    store._pool = pool
    store._embedder = None
    store._client = None
    store._log = MagicMock()
    return store, conn


# ── propose_events ────────────────────────────────────────────────────────────

async def test_propose_events_inserts_each_event():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.execute = AsyncMock()

    events = [
        Event(id=None, event_type="meeting", title="Sprint planning"),
        Event(id=None, event_type="call", title="Customer call"),
    ]
    await store.propose_events(events)

    assert conn.execute.call_count == 2


async def test_propose_events_empty_list_does_nothing():
    store, conn = _make_store()
    conn.execute = AsyncMock()
    await store.propose_events([])
    conn.execute.assert_not_called()


async def test_propose_events_continues_on_single_failure():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.execute = AsyncMock(side_effect=[RuntimeError("DB error"), None])

    events = [
        Event(id=None, event_type="meeting", title="Fails"),
        Event(id=None, event_type="call", title="Succeeds"),
    ]
    # Should not raise — second event still processed
    await store.propose_events(events)
    assert conn.execute.call_count == 2


# ── propose_procedure ─────────────────────────────────────────────────────────

async def test_propose_procedure_inserts_record():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.execute = AsyncMock()

    proc = Procedure(
        id=None,
        name="Send outreach emails",
        trigger="When user wants to contact prospects",
        preconditions=["Have a target list"],
        steps=["Draft email", "Review", "Send"],
        success_criteria=["All emails sent"],
    )
    await store.propose_procedure(proc)

    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert "memory_procedures" in call_args[0]


async def test_propose_procedure_swallows_db_error():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.execute = AsyncMock(side_effect=RuntimeError("constraint"))

    proc = Procedure(id=None, name="Test", trigger="trigger", steps=["step"])
    await store.propose_procedure(proc)  # Must not raise


# ── upsert_entity ─────────────────────────────────────────────────────────────

async def test_upsert_entity_returns_id():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    new_id = uuid4()
    conn.fetchrow = AsyncMock(return_value={"id": new_id})

    entity = Entity(
        id=None,
        entity_type="person",
        canonical_name="Alice Wonderland",
        aliases=["Alice"],
        attrs={"relationship": "colleague"},
    )
    result = await store.upsert_entity(entity)

    assert result == new_id
    conn.fetchrow.assert_called_once()
    sql = conn.fetchrow.call_args[0][0]
    assert "memory_entities" in sql
    assert "ON CONFLICT" in sql


async def test_upsert_entity_passes_correct_fields():
    pool, conn = _make_pool()
    store, conn = _make_store(pool)
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})

    entity = Entity(
        id=None,
        entity_type="organisation",
        canonical_name="Acme Corp",
        aliases=["Acme"],
        attrs={"domain": "technology"},
    )
    await store.upsert_entity(entity)

    args = conn.fetchrow.call_args[0]
    assert "organisation" in args
    assert "Acme Corp" in args
