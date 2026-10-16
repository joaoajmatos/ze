from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_priority.errors import StalePriorityRestoreError
from ze_priority.store import PostgresPriorityOverrideStore

UTC = timezone.utc
T0 = datetime(2026, 10, 1, tzinfo=UTC)
T1 = datetime(2026, 10, 2, tzinfo=UTC)


def _row(**overrides) -> dict:
    base = dict(
        id=uuid4(),
        source_kind="loop",
        source_id=uuid4(),
        anchor_source_kind="goal",
        anchor_source_id=uuid4(),
        relation="above",
        pinned=False,
        submitted_at=T1,
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )
    base.update(overrides)
    return base


def _conn() -> AsyncMock:
    conn = AsyncMock()

    @asynccontextmanager
    async def _transaction():
        yield

    conn.transaction = _transaction
    return conn


def _store(conn: AsyncMock) -> PostgresPriorityOverrideStore:
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return PostgresPriorityOverrideStore(pool=pool)


def _inserts(conn: AsyncMock) -> list:
    return [c for c in conn.fetchrow.await_args_list if "INSERT INTO" in c.args[0]]


async def test_restore_with_prior_reinstates_a_copy():
    new = _row(submitted_at=T1)
    prior = _row(
        source_id=new["source_id"], submitted_at=T0, superseded_at=T1, pinned=True
    )
    conn = _conn()
    conn.fetchrow.side_effect = [new, prior, prior]
    store = _store(conn)

    await store.restore(new["id"], prior["id"])

    update_sql = conn.execute.await_args_list[0].args[0]
    assert "superseded_at" in update_sql
    assert conn.execute.await_args_list[0].args[1] == new["id"]
    insert_args = _inserts(conn)[0].args
    assert insert_args[1] != prior["id"]  # new id
    assert insert_args[1] != new["id"]
    assert prior["anchor_source_id"] in insert_args
    assert prior["relation"] in insert_args
    assert T0 in insert_args  # prior's submitted_at kept
    assert prior["contribution_domain_id"] in insert_args


async def test_restore_without_prior_only_supersedes_new_row():
    new = _row()
    conn = _conn()
    conn.fetchrow.side_effect = [new]
    store = _store(conn)

    result = await store.restore(new["id"], None)

    assert result is None
    conn.execute.assert_awaited_once()
    assert _inserts(conn) == []


async def test_restore_prior_superseded_by_something_else_only_supersedes_new():
    new = _row(submitted_at=T1)
    prior = _row(
        source_id=new["source_id"],
        submitted_at=T0,
        superseded_at=T1 + timedelta(hours=1),
    )
    conn = _conn()
    conn.fetchrow.side_effect = [new, prior]
    store = _store(conn)

    result = await store.restore(new["id"], prior["id"])

    assert result is None
    conn.execute.assert_awaited_once()
    assert _inserts(conn) == []


async def test_restore_fails_when_override_no_longer_active():
    conn = _conn()
    conn.fetchrow.side_effect = [None]
    store = _store(conn)

    with pytest.raises(StalePriorityRestoreError):
        await store.restore(uuid4(), uuid4())

    conn.execute.assert_not_awaited()
    assert _inserts(conn) == []


async def test_restore_missing_prior_row_only_supersedes_new():
    new = _row()
    conn = _conn()
    conn.fetchrow.side_effect = [new, None]
    store = _store(conn)

    assert await store.restore(new["id"], uuid4()) is None
    conn.execute.assert_awaited_once()
