"""Undo payloads for set_reminder (Phase 180)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_calendar.agents.reminders.agent import RemindersAgent
from ze_calendar.agents.reminders.tools import cancel_reminder, set_reminder
from ze_calendar.reminders.store import Reminder


def _future() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


async def test_set_reminder_returns_undo_payload_on_success():
    rid = uuid4()
    store = AsyncMock()
    store.create = AsyncMock(return_value=rid)
    result = await set_reminder(
        store=store,
        scheduler=MagicMock(),
        notifier=AsyncMock(),
        label="call Ana",
        fire_at=_future(),
    )
    assert result["undo"] == {"reminder_id": str(rid)}
    assert result["id"] == str(rid)


async def test_set_reminder_no_payload_on_parse_error():
    result = await set_reminder(
        store=AsyncMock(),
        scheduler=MagicMock(),
        notifier=AsyncMock(),
        label="x",
        fire_at="not a date",
    )
    assert "error" in result
    assert "undo" not in result


async def test_set_reminder_no_payload_on_past_time():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    result = await set_reminder(
        store=AsyncMock(),
        scheduler=MagicMock(),
        notifier=AsyncMock(),
        label="x",
        fire_at=past,
    )
    assert "error" in result
    assert "undo" not in result


async def test_cancel_reminder_on_already_fired_reminder():
    """A fired reminder row still exists (sent=True); cancel deletes it and reports success."""
    rid = uuid4()
    now = datetime.now(timezone.utc)
    fired = Reminder(
        id=rid,
        label="call Ana",
        fire_at=now - timedelta(minutes=5),
        created_at=now - timedelta(hours=1),
        sent=True,
        sent_at=now - timedelta(minutes=5),
    )
    store = AsyncMock()
    store.get = AsyncMock(return_value=fired)
    scheduler = MagicMock()
    result = await cancel_reminder(
        store=store, scheduler=scheduler, reminder_id=str(rid)
    )
    assert result == {"cancelled": "call Ana"}
    store.delete.assert_awaited_once_with(rid)


def test_tool_deps_has_the_keys_the_loop_used():
    store, scheduler, notifier = AsyncMock(), MagicMock(), AsyncMock()
    from tests.support.settings import make_settings

    agent = RemindersAgent(
        openrouter_client=AsyncMock(),
        reminder_store=store,
        workflow_scheduler=scheduler,
        notifier=notifier,
        settings=make_settings(),
    )
    assert agent.tool_deps() == {
        "store": store,
        "scheduler": scheduler,
        "notifier": notifier,
    }
