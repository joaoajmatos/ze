from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_automation.goals import STUCK_IDLE_DAYS
from ze_automation.goals.postgres import PostgresGoalStore

NOW = datetime.now(UTC)


def _row(**overrides) -> dict:
    row = {
        "id": uuid4(),
        "title": "Launch LedgerLite",
        "objective": "Ship",
        "success_condition": "Live",
        "time_horizon": "1 month",
        "status": "active",
        "type": "one_shot",
        "retrospective_text": None,
        "last_stuck_alert_at": None,
        "created_at": NOW - timedelta(days=30),
        "updated_at": NOW,
        "milestones_done": 0,
        "milestones_total": 0,
        "last_progress_at": None,
        "next_milestone": None,
        "gate_id": None,
        "gate_title": None,
        "gate_open_since": None,
    }
    row.update(overrides)
    return row


def _store(rows: list[dict]) -> tuple[PostgresGoalStore, AsyncMock]:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return PostgresGoalStore(pool), conn


async def test_stuck_idle_days_is_seven():
    assert STUCK_IDLE_DAYS == 7


async def test_counts_next_milestone_and_gate_come_through():
    gate_id = uuid4()
    fired = NOW - timedelta(days=1)
    store, conn = _store(
        [
            _row(
                milestones_done=2,
                milestones_total=5,
                next_milestone="Draft the landing page",
                last_progress_at=NOW - timedelta(days=1),
                gate_id=gate_id,
                gate_title="Approve pricing",
                gate_open_since=fired,
            )
        ]
    )

    [progress] = await store.list_progress()

    assert progress.milestones_done == 2
    assert progress.milestones_total == 5
    assert progress.next_milestone == "Draft the landing page"
    assert progress.gate_id == gate_id
    assert progress.gate_title == "Approve pricing"
    assert progress.gate_open_since == fired
    assert progress.stuck_since is None
    assert conn.fetch.await_count == 1


async def test_active_goal_idle_for_a_week_is_stuck_since_last_progress():
    last = NOW - timedelta(days=STUCK_IDLE_DAYS + 1)
    store, _ = _store(
        [_row(milestones_done=1, milestones_total=3, last_progress_at=last)]
    )

    [progress] = await store.list_progress()

    assert progress.last_progress_at == last
    assert progress.stuck_since == last


async def test_recent_progress_is_not_stuck():
    store, _ = _store([_row(last_progress_at=NOW - timedelta(days=2))])

    [progress] = await store.list_progress()

    assert progress.stuck_since is None


async def test_active_goal_without_a_completed_milestone_uses_created_at():
    created = NOW - timedelta(days=20)
    store, _ = _store([_row(created_at=created, last_progress_at=None)])

    [progress] = await store.list_progress()

    assert progress.last_progress_at is None
    assert progress.stuck_since == created


async def test_awaiting_gate_goal_is_stuck_since_the_gate_fired():
    fired = NOW - timedelta(days=STUCK_IDLE_DAYS + 2)
    store, _ = _store(
        [
            _row(
                status="awaiting_gate",
                last_progress_at=NOW - timedelta(days=1),
                gate_id=uuid4(),
                gate_title="Approve pricing",
                gate_open_since=fired,
            )
        ]
    )

    [progress] = await store.list_progress()

    assert progress.stuck_since == fired


async def test_recently_fired_gate_is_not_stuck():
    store, _ = _store(
        [
            _row(
                status="awaiting_gate",
                gate_id=uuid4(),
                gate_title="Approve",
                gate_open_since=NOW - timedelta(days=1),
            )
        ]
    )

    [progress] = await store.list_progress()

    assert progress.stuck_since is None


async def test_alert_cooldown_column_does_not_affect_stuck_since():
    last = NOW - timedelta(days=10)
    store, _ = _store([_row(last_progress_at=last, last_stuck_alert_at=NOW)])

    [progress] = await store.list_progress()

    assert progress.stuck_since == last


async def test_paused_and_planning_goals_are_never_stuck():
    store, _ = _store([_row(status="paused"), _row(status="planning")])

    progress = await store.list_progress()

    assert [p.stuck_since for p in progress] == [None, None]
