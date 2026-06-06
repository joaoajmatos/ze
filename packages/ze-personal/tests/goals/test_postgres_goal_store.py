from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_personal.goals.postgres import PostgresGoalStore
from ze_personal.goals.types import ExecutionTrace


def _make_pool(fetchrow=None, fetch=None, execute=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock(return_value=execute)

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


def _make_conn_with_transaction(fetchrow=None, fetch=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def transaction():
        yield

    conn.transaction = transaction

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


def _trace(milestone_id=None, goal_id=None, seq=0) -> ExecutionTrace:
    return ExecutionTrace(
        milestone_id=milestone_id or uuid4(),
        goal_id=goal_id or uuid4(),
        seq=seq,
        tool_name="search_web",
        args={"query": "test"},
        result="Some results",
        duration_ms=123,
        success=True,
        error=None,
    )


# ── save_traces / list_traces ─────────────────────────────────────────────────

async def test_save_traces_inserts_each_trace():
    pool, conn = _make_conn_with_transaction()
    store = PostgresGoalStore(pool)

    mid = uuid4()
    gid = uuid4()
    traces = [_trace(milestone_id=mid, goal_id=gid, seq=i) for i in range(3)]

    await store.save_traces(traces)

    assert conn.execute.call_count == 3
    call_args = conn.execute.call_args_list[0].args
    assert "goal_execution_traces" in call_args[0]
    assert call_args[1] == mid  # milestone_id


async def test_save_traces_no_op_on_empty_list():
    pool, conn = _make_conn_with_transaction()
    store = PostgresGoalStore(pool)
    await store.save_traces([])
    conn.execute.assert_not_called()


async def test_list_traces_maps_rows():
    mid = uuid4()
    gid = uuid4()
    row = {
        "id": uuid4(),
        "milestone_id": mid,
        "goal_id": gid,
        "seq": 0,
        "tool_name": "search_web",
        "args": json.dumps({"query": "test"}),
        "result": "results",
        "duration_ms": 50,
        "success": True,
        "error": None,
        "created_at": None,
    }
    pool, _ = _make_pool(fetch=[row])
    store = PostgresGoalStore(pool)

    traces = await store.list_traces(mid)

    assert len(traces) == 1
    t = traces[0]
    assert t.milestone_id == mid
    assert t.goal_id == gid
    assert t.tool_name == "search_web"
    assert t.args == {"query": "test"}
    assert t.success is True


async def test_list_traces_returns_empty_for_unknown_milestone():
    pool, _ = _make_pool(fetch=[])
    store = PostgresGoalStore(pool)
    traces = await store.list_traces(uuid4())
    assert traces == []


# ── increment_consecutive_failures ───────────────────────────────────────────

async def test_increment_consecutive_failures_returns_new_count():
    pool, conn = _make_pool(fetchrow={"consecutive_failures": 2})
    store = PostgresGoalStore(pool)

    count = await store.increment_consecutive_failures(uuid4())

    assert count == 2
    sql = conn.fetchrow.call_args.args[0]
    assert "consecutive_failures + 1" in sql
    assert "RETURNING" in sql


async def test_increment_consecutive_failures_returns_zero_when_no_row():
    pool, conn = _make_pool(fetchrow=None)
    store = PostgresGoalStore(pool)
    count = await store.increment_consecutive_failures(uuid4())
    assert count == 0


async def test_reset_consecutive_failures_executes_update():
    pool, conn = _make_pool()
    store = PostgresGoalStore(pool)
    gid = uuid4()

    await store.reset_consecutive_failures(gid)

    conn.execute.assert_called_once()
    sql = conn.execute.call_args.args[0]
    assert "consecutive_failures = 0" in sql


# ── increment_replan_count ────────────────────────────────────────────────────

async def test_increment_replan_count_returns_new_count():
    pool, conn = _make_pool(fetchrow={"replan_count": 1})
    store = PostgresGoalStore(pool)

    count = await store.increment_replan_count(uuid4())

    assert count == 1
    sql = conn.fetchrow.call_args.args[0]
    assert "replan_count + 1" in sql
    assert "RETURNING" in sql


async def test_increment_replan_count_returns_zero_when_no_row():
    pool, conn = _make_pool(fetchrow=None)
    store = PostgresGoalStore(pool)
    count = await store.increment_replan_count(uuid4())
    assert count == 0


async def test_replan_count_has_no_reset_method():
    """replan_count is a lifetime counter — no reset path should exist."""
    store = PostgresGoalStore.__dict__
    assert "reset_replan_count" not in store
