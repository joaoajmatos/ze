from unittest.mock import AsyncMock, MagicMock

from ze_calendar.reminders.calendar_store import CalendarReminderStore


def _pool():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=cm)
    return pool, conn


async def test_list_unsent_defaults_to_upcoming_only():
    pool, conn = _pool()
    store = CalendarReminderStore(pool)

    await store.list_unsent()

    sql = conn.fetch.call_args.args[0]
    assert "sent = false" in sql
    assert "fire_at > NOW()" in sql


async def test_list_unsent_include_overdue_drops_now_filter():
    pool, conn = _pool()
    store = CalendarReminderStore(pool)

    await store.list_unsent(include_overdue=True)

    sql = conn.fetch.call_args.args[0]
    assert "sent = false" in sql
    assert "fire_at > NOW()" not in sql
