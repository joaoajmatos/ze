from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_calendar.reminders.store import Reminder
from ze_calendar.screen_resolvers import ReminderScreenResolver
from ze_sdk.screen import ResolveContext, ScreenRef, ScreenStatus

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)


async def test_reminder_line_for_pending_and_sent_and_missing():
    rid = uuid4()
    pending = Reminder(
        id=rid,
        label="Call Ana",
        fire_at=NOW + timedelta(days=1),
        created_at=NOW,
        sent=False,
        sent_at=None,
    )
    sent = Reminder(
        id=rid,
        label="Call Ana",
        fire_at=NOW - timedelta(hours=2),
        created_at=NOW,
        sent=True,
        sent_at=NOW,
    )
    store = AsyncMock()
    ref = ScreenRef(kind="reminder", id=str(rid))
    store.get = AsyncMock(return_value=pending)
    [line] = await ReminderScreenResolver(store).resolve([ref], ResolveContext(now=NOW))
    assert line.label == "Call Ana" and line.summary == "fires 2026-10-18 14:00 UTC"
    store.get = AsyncMock(return_value=sent)
    [line] = await ReminderScreenResolver(store).resolve([ref], ResolveContext(now=NOW))
    assert line.summary == "fired 2 h ago"
    store.get = AsyncMock(return_value=None)
    [gone] = await ReminderScreenResolver(store).resolve([ref], ResolveContext(now=NOW))
    assert gone.status is ScreenStatus.MISSING
