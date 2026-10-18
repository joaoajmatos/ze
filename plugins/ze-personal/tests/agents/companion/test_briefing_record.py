"""Companion answers questions about a sent briefing from the stored record."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from ze_agents.tool import ToolAccess, get_tool
from ze_news.agents.agent import NewsAgent
from ze_personal.agents.companion.agent import _AGENT_INSTRUCTIONS, CompanionAgent
from ze_personal.agents.companion.tools import get_briefing
from ze_proactive.types import NotificationRow

SENT = datetime(2026, 10, 18, 6, 34, tzinfo=timezone.utc)


def _row(*, delivery="delivered", read_at=None, delivered_at=SENT):
    return NotificationRow(
        id="n1",
        event_type="morning_brief",
        source="personal",
        title="Morning Briefing",
        body="Good morning!\n📋 Unreviewed facts: 9",
        target_type=None,
        target_id=None,
        created_at=SENT,
        read_at=read_at,
        delivery=delivery,
        delivered_at=delivered_at,
    )


def _store(rows):
    store = AsyncMock()
    store.latest_by_event = AsyncMock(return_value=rows)
    return store


def test_tool_is_a_read_tool_on_the_companion():
    assert "get_briefing" in CompanionAgent.tools
    assert get_tool("get_briefing").access is ToolAccess.READ


def test_instructions_name_the_tool_and_ban_substituting_news():
    assert "get_briefing" in _AGENT_INSTRUCTIONS
    assert "never fetch news" in _AGENT_INSTRUCTIONS


def test_news_no_longer_claims_the_morning_briefing():
    assert "briefing" not in NewsAgent.description.lower()


async def test_latest_briefing_reports_what_was_sent_and_not_yet_read():
    out = await get_briefing(notification_store=_store([_row()]))
    assert out["found"] is True
    b = out["briefings"][0]
    assert b["sent_at"] == SENT.isoformat()
    assert b["delivery"] == "delivered"
    assert b["opened"] is False and b["opened_at"] is None
    assert "Unreviewed facts: 9" in b["body"]


async def test_read_briefing_carries_the_opened_time():
    read = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
    out = await get_briefing(notification_store=_store([_row(read_at=read)]))
    assert out["briefings"][0]["opened"] is True
    assert out["briefings"][0]["opened_at"] == read.isoformat()


async def test_held_briefing_is_not_reported_as_sent():
    out = await get_briefing(
        notification_store=_store([_row(delivery="held", delivered_at=None)])
    )
    b = out["briefings"][0]
    assert b["delivery"] == "held" and b["sent_at"] is None


async def test_no_briefing_yet_says_so():
    out = await get_briefing(notification_store=_store([]))
    assert out == {"found": False, "briefings": []}
    json.dumps(out)


async def test_count_is_clamped_and_queries_morning_brief():
    store = _store([_row()])
    await get_briefing(notification_store=store, count=99)
    store.latest_by_event.assert_awaited_once_with("morning_brief", limit=5)


async def test_a_store_failure_is_an_error_not_an_empty_answer():
    store = AsyncMock()
    store.latest_by_event = AsyncMock(side_effect=RuntimeError("db down"))
    out = await get_briefing(notification_store=store)
    assert out["found"] is False and out["error"]
