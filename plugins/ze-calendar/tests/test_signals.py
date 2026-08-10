"""Tests for CalendarSignalSource (Claim Topology, FR-013)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind

from ze_calendar.reminders.calendar_store import CalendarReminder
from ze_calendar.signals import CalendarSignalSource


def _reminder(**kwargs) -> CalendarReminder:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        event_id="evt1",
        event_title="Standup",
        fire_at=now + timedelta(hours=1),
        label="15 min before",
        sent=False,
        assessed_at=now,
    )
    defaults.update(kwargs)
    return CalendarReminder(**defaults)


async def test_source_key():
    assert CalendarSignalSource.source_key == "calendar"


async def test_signal_carries_fact_claim_kind_and_confidence():
    store = AsyncMock()
    store.list_unsent = AsyncMock(return_value=[_reminder()])
    source = CalendarSignalSource(store)

    since = datetime.now(timezone.utc) - timedelta(days=1)
    [signal] = await source.poll(since)

    assert signal.claim_kind == ClaimKind.FACT
    assert signal.confidence != signal.magnitude


async def test_reminder_before_since_is_excluded():
    store = AsyncMock()
    store.list_unsent = AsyncMock(
        return_value=[_reminder(assessed_at=datetime(2000, 1, 1, tzinfo=timezone.utc))]
    )
    source = CalendarSignalSource(store)

    since = datetime.now(timezone.utc) - timedelta(days=1)
    signals = await source.poll(since)
    assert signals == []
