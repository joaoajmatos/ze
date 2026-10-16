from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from ze_automation.holds.store import PostgresHeldWriteStore
from ze_automation.holds.types import HeldWrite, HeldWriteStatus

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


def _make_pool(fetchrow=None, fetch=None, fetchval=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.fetchval = AsyncMock(return_value=fetchval)
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


def _row(**overrides):
    row = {
        "request_id": "req-1",
        "source": "workflow",
        "owner_ref": "exec-1",
        "items": json.dumps([{"item_id": "a", "effect": "Send an email"}]),
        "payload": json.dumps({"thread_id": "t-1"}),
        "status": "open",
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=24),
        "decided_at": None,
    }
    row.update(overrides)
    return row


def _hold() -> HeldWrite:
    return HeldWrite(
        request_id="req-1",
        source="workflow",
        owner_ref="exec-1",
        items=[{"item_id": "a", "effect": "Send an email"}],
        payload={"thread_id": "t-1"},
        expires_at=NOW + timedelta(hours=24),
    )


async def test_create_inserts_json_encoded_items_and_payload():
    pool, conn = _make_pool()
    store = PostgresHeldWriteStore(pool)

    await store.create(_hold())

    sql, *args = conn.execute.call_args.args
    assert "INSERT INTO held_writes" in sql
    assert args[0] == "req-1"
    assert args[1] == "workflow"
    assert args[2] == "exec-1"
    assert json.loads(args[3]) == [{"item_id": "a", "effect": "Send an email"}]
    assert json.loads(args[4]) == {"thread_id": "t-1"}
    assert args[5] == "open"
    assert args[6] == NOW + timedelta(hours=24)


async def test_get_decodes_jsonb_columns():
    pool, _ = _make_pool(fetchrow=_row())
    store = PostgresHeldWriteStore(pool)

    held = await store.get("req-1")

    assert held is not None
    assert held.status is HeldWriteStatus.OPEN
    assert held.items == [{"item_id": "a", "effect": "Send an email"}]
    assert held.payload == {"thread_id": "t-1"}
    assert held.expires_at == NOW + timedelta(hours=24)


async def test_get_returns_none_when_missing():
    pool, _ = _make_pool(fetchrow=None)
    store = PostgresHeldWriteStore(pool)

    assert await store.get("missing") is None


async def test_list_filters_by_status():
    pool, conn = _make_pool(fetch=[_row()])
    store = PostgresHeldWriteStore(pool)

    held = await store.list(HeldWriteStatus.OPEN)

    sql, status = conn.fetch.call_args.args
    assert "WHERE status = $1" in sql
    assert status == "open"
    assert [h.request_id for h in held] == ["req-1"]


async def test_decide_only_moves_open_holds():
    pool, conn = _make_pool(fetchval="req-1")
    store = PostgresHeldWriteStore(pool)

    decided = await store.decide("req-1", HeldWriteStatus.APPROVED)

    sql, *args = conn.fetchval.call_args.args
    assert "status = 'open'" in sql
    assert args[0] == "req-1"
    assert args[1] == "approved"
    assert decided is True


async def test_decide_twice_returns_false_the_second_time():
    pool, _ = _make_pool(fetchval=None)
    store = PostgresHeldWriteStore(pool)

    assert await store.decide("req-1", HeldWriteStatus.DENIED) is False


async def test_list_expired_selects_open_holds_past_their_deadline():
    pool, conn = _make_pool(fetch=[])
    store = PostgresHeldWriteStore(pool)

    assert await store.list_expired(NOW) == []

    sql, now = conn.fetch.call_args.args
    assert "status = 'open'" in sql
    assert "expires_at <= $1" in sql
    assert now == NOW
