"""Calendar and reminder confirmations name the item, not its id (Phase 181, e2e finding 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_calendar.agents.calendar.tools import _event_change_label, _event_label
from ze_calendar.agents.reminders.tools import _reminder_label


def _credentials(event: dict) -> MagicMock:
    credentials = MagicMock()
    events = credentials.calendar.return_value.events.return_value
    events.get.return_value.execute.return_value = event
    return credentials


async def test_a_reminder_is_named_by_its_label_and_time() -> None:
    store = AsyncMock()
    store.get = AsyncMock(
        return_value=SimpleNamespace(
            label="Pay rent", fire_at=datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)
        )
    )

    summary = await _reminder_label({"reminder_id": str(uuid4()), "store": store})

    assert summary == '"Pay rent" at 2026-10-17 09:00 UTC'


async def test_an_event_is_named_by_its_title_and_start() -> None:
    credentials = _credentials(
        {"summary": "Dentist", "start": {"dateTime": "2026-10-17T15:00:00+01:00"}}
    )

    summary = await _event_label({"event_id": "evt_1", "credentials": credentials})

    assert summary == '"Dentist" 2026-10-17T15:00:00+01:00'
    events = credentials.calendar.return_value.events.return_value
    events.get.assert_called_once_with(calendarId="primary", eventId="evt_1")


async def test_an_event_change_lists_what_changes() -> None:
    credentials = _credentials({"summary": "Dentist", "start": {"date": "2026-10-17"}})

    summary = await _event_change_label(
        {"event_id": "evt_1", "credentials": credentials, "start": "16:00"}
    )

    assert summary == '"Dentist" 2026-10-17 → start: 16:00'
