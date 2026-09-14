from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_priority.errors import PriorityOverrideNotFoundError
from ze_priority.store import PostgresPriorityOverrideStore
from ze_priority.types import PriorityOverride

UTC = timezone.utc


def _row(**overrides) -> dict:
    base = dict(
        id=uuid4(),
        source_kind="loop",
        source_id=uuid4(),
        anchor_source_kind="goal",
        anchor_source_id=uuid4(),
        relation="above",
        pinned=False,
        submitted_at=datetime.now(UTC),
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )
    base.update(overrides)
    return base


def _pool_with(conn: AsyncMock) -> MagicMock:
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool


def _transaction_conn() -> AsyncMock:
    conn = AsyncMock()

    @asynccontextmanager
    async def _transaction():
        yield

    conn.transaction = _transaction
    return conn


async def test_create_persists_and_returns_override():
    conn = _transaction_conn()
    row = _row()
    conn.fetchrow.return_value = row
    store = PostgresPriorityOverrideStore(pool=_pool_with(conn))

    override = PriorityOverride(
        id=row["id"],
        source_kind="loop",
        source_id=row["source_id"],
        anchor_source_kind="goal",
        anchor_source_id=row["anchor_source_id"],
        relation="above",
        pinned=False,
        submitted_at=row["submitted_at"],
        superseded_at=None,
        contribution_domain_id=row["contribution_domain_id"],
    )
    result = await store.create(override)

    assert result.id == row["id"]
    conn.execute.assert_awaited_once()  # supersede UPDATE ran first
    conn.fetchrow.assert_awaited_once()


async def test_get_active_excludes_superseded():
    conn = AsyncMock()
    conn.fetch.return_value = [_row()]
    store = PostgresPriorityOverrideStore(pool=_pool_with(conn))

    results = await store.get_active()

    assert len(results) == 1
    query = conn.fetch.await_args.args[0]
    assert "superseded_at IS NULL" in query


async def test_get_returns_none_when_missing():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    store = PostgresPriorityOverrideStore(pool=_pool_with(conn))

    result = await store.get(uuid4())

    assert result is None


async def test_unpin_clears_pinned_flag():
    conn = AsyncMock()
    row = _row(pinned=False)
    conn.fetchrow.return_value = row
    store = PostgresPriorityOverrideStore(pool=_pool_with(conn))

    result = await store.unpin(row["id"])

    assert result.pinned is False


async def test_unpin_raises_when_no_active_row_matches():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    store = PostgresPriorityOverrideStore(pool=_pool_with(conn))

    with pytest.raises(PriorityOverrideNotFoundError):
        await store.unpin(uuid4())
