from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from ze_memory.action_records.store import (
    PostgresActionRecordStore,
    _context_from_json,
    _context_to_json,
)
from ze_memory.action_records.types import ActionContext


def test_script_key_round_trips_through_context_json():
    ctx = ActionContext(script_key="abc123")
    assert _context_to_json(ctx)["script_key"] == "abc123"
    assert _context_from_json(_context_to_json(ctx)).script_key == "abc123"
    assert _context_from_json({}).script_key is None


async def test_list_by_script_key_filters_newest_first_and_clamps_limit():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    store = PostgresActionRecordStore(pool)
    assert await store.list_by_script_key("k1") == []
    sql, *args = conn.fetch.await_args.args
    assert "context->>'script_key' = $1::text" in sql
    assert "authoritative_domain = 'workspace.tool_script'" in sql
    assert "ORDER BY occurred_at DESC, id DESC" in sql
    assert args == ["k1", 3]
    await store.list_by_script_key("k1", limit=9999)
    assert conn.fetch.await_args.args[-1] == 500
