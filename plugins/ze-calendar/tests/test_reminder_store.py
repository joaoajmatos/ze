from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_calendar.reminders.store import ReminderStore

NOW = datetime(2026, 10, 17, 9, tzinfo=timezone.utc)


def _store(rows):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return ReminderStore(pool), conn


def _row(**kw):
    return {
        "id": uuid4(),
        "label": "Call the bank",
        "fire_at": NOW,
        "created_at": NOW,
        "sent": False,
        "sent_at": None,
        "due": False,
        **kw,
    }


@pytest.mark.parametrize(
    "status,fragments,order",
    [
        ("upcoming", ["sent = false", "fire_at > NOW()"], "ORDER BY fire_at ASC"),
        ("overdue", ["sent = false", "fire_at <= NOW()"], "ORDER BY fire_at ASC"),
        ("fired", ["sent = true"], "ORDER BY sent_at DESC NULLS LAST"),
        ("all", [], "ORDER BY fire_at DESC"),
    ],
)
async def test_list_by_status_sql(status, fragments, order):
    store, conn = _store([])

    await store.list_by_status(status, 25)

    sql, *params = conn.fetch.await_args.args
    for fragment in fragments:
        assert fragment in sql
    assert order in sql
    assert "fire_at <= NOW() AS due" in sql
    assert params == [25]


async def test_all_has_no_status_filter():
    store, conn = _store([])
    await store.list_by_status("all", 5)
    assert "WHERE" not in conn.fetch.await_args.args[0]


async def test_returns_reminder_with_due_flag():
    store, _ = _store([_row(due=True), _row(sent=True, sent_at=NOW)])

    [(first, due1), (second, due2)] = await store.list_by_status("all", 10)

    assert first.label == "Call the bank" and due1 is True
    assert second.sent is True and due2 is False
