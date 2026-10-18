from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.action_records.store import PostgresActionRecordStore
from ze_memory.action_records.types import ActionSubjectKind

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


def _store():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return PostgresActionRecordStore(pool), conn


def _call(conn):
    sql, *args = conn.fetch.await_args.args
    return " ".join(sql.split()), args


async def test_subject_uses_mapped_key_and_text_cast():
    store, conn = _store()
    sid = uuid4()
    await store.list_by_subject(kind=ActionSubjectKind.WORKFLOW_RUN, subject_id=sid)
    sql, args = _call(conn)
    assert "context->>'workflow_run_id' = $1::text" in sql
    assert args[0] == str(sid)


async def test_each_kind_maps_to_its_own_key():
    for kind, key in (
        (ActionSubjectKind.GOAL, "goal_id"),
        (ActionSubjectKind.WORKFLOW, "workflow_id"),
        (ActionSubjectKind.WORKSPACE_RUN, "workspace_run_id"),
    ):
        store, conn = _store()
        await store.list_by_subject(kind=kind, subject_id=uuid4())
        sql, _ = _call(conn)
        assert f"context->>'{key}' = $1::text" in sql


async def test_no_subject_has_no_context_clause():
    store, conn = _store()
    await store.list_by_subject()
    sql, args = _call(conn)
    assert "context->>" not in sql
    assert "WHERE" not in sql
    assert args == [50]


async def test_since_uses_timestamptz_cast():
    store, conn = _store()
    await store.list_by_subject(since=NOW)
    sql, args = _call(conn)
    assert "occurred_at > $1::timestamptz" in sql
    assert args[0] == NOW


async def test_cursor_clause_only_when_given():
    store, conn = _store()
    await store.list_by_subject()
    sql, _ = _call(conn)
    assert "(occurred_at, id) <" not in sql

    rid = uuid4()
    await store.list_by_subject(cursor=(NOW, rid))
    sql, args = _call(conn)
    assert "(occurred_at, id) < ($1::timestamptz, $2::uuid)" in sql
    assert args[:2] == [NOW, rid]


async def test_order_and_limit():
    store, conn = _store()
    await store.list_by_subject(limit=7)
    sql, args = _call(conn)
    assert sql.endswith("ORDER BY occurred_at DESC, id DESC LIMIT $1")
    assert args == [7]


async def test_all_filters_number_params_in_order():
    store, conn = _store()
    sid, rid = uuid4(), uuid4()
    await store.list_by_subject(
        kind=ActionSubjectKind.GOAL,
        subject_id=sid,
        since=NOW,
        cursor=(NOW, rid),
        limit=3,
    )
    sql, args = _call(conn)
    assert "$1::text" in sql and "$2::timestamptz" in sql
    assert "($3::timestamptz, $4::uuid)" in sql and sql.endswith("LIMIT $5")
    assert args == [str(sid), NOW, NOW, rid, 3]
