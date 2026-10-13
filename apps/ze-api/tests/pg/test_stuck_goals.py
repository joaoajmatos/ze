from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from ze_automation.goals.postgres import PostgresGoalStore
from ze_automation.jobs.stuck_goals import StuckGoalJob
from ze_correlation.store import PostgresHypothesisStore
from ze_priority.view import PriorityView
from ze_worldstate.store import PostgresLoopStore

from tests.pg._builders import make_goal_with_gates, utcnow

pytestmark = pytest.mark.pg


def _dev_shape_gates():
    now = utcnow()
    return [
        ("approved", now - timedelta(days=40), True),
        ("awaiting_approval", now - timedelta(days=10), False),
        ("pending", None, False),
        ("pending", None, False),
        ("pending", None, False),
    ]


async def test_dev_shape_yields_one_entry(pg_pool):
    goal_id = await make_goal_with_gates(
        pg_pool, status="awaiting_gate", gates=_dev_shape_gates()
    )
    stuck = await PostgresGoalStore(pg_pool).list_stuck(
        idle_days=7, alert_cooldown_days=14
    )
    assert len(stuck) == 1
    entry = stuck[0]
    assert entry.goal.id == goal_id and entry.kind == "awaiting_gate"
    assert entry.idle_days == 10
    assert entry.gate.status.value == "awaiting_approval"


async def test_two_fired_open_gates_use_the_earliest(pg_pool):
    now = utcnow()
    await make_goal_with_gates(
        pg_pool,
        status="awaiting_gate",
        gates=[
            ("pending", now - timedelta(days=12), False),
            ("pending", now - timedelta(days=5), False),
        ],
    )
    stuck = await PostgresGoalStore(pg_pool).list_stuck(
        idle_days=1, alert_cooldown_days=14
    )
    assert len(stuck) == 1 and stuck[0].idle_days == 12


async def test_only_unfired_gates_yield_nothing(pg_pool):
    await make_goal_with_gates(
        pg_pool,
        status="awaiting_gate",
        gates=[("pending", None, False), ("pending", None, False)],
    )
    assert (
        await PostgresGoalStore(pg_pool).list_stuck(idle_days=0, alert_cooldown_days=0)
        == []
    )


async def test_active_goal_with_old_milestone_is_stuck(pg_pool):
    goal_id = await make_goal_with_gates(pg_pool, status="active")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO goal_milestones (goal_id, title, description, sequence, status, completed_at)
            VALUES ($1, 'First', 'd', 1, 'completed', now() - interval '20 days')
            """,
            goal_id,
        )
    stuck = await PostgresGoalStore(pg_pool).list_stuck(
        idle_days=7, alert_cooldown_days=14
    )
    assert [(s.goal.id, s.kind) for s in stuck] == [(goal_id, "active")]


async def test_recent_alert_is_in_cooldown(pg_pool):
    goal_id = await make_goal_with_gates(
        pg_pool,
        status="awaiting_gate",
        gates=[("pending", utcnow() - timedelta(days=10), False)],
    )
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE goals SET last_stuck_alert_at = now() - interval '3 days' WHERE id = $1",
            goal_id,
        )
    assert (
        await PostgresGoalStore(pg_pool).list_stuck(idle_days=7, alert_cooldown_days=14)
        == []
    )


async def test_priority_view_call_shape_does_not_raise(pg_pool):
    await make_goal_with_gates(
        pg_pool, status="awaiting_gate", gates=_dev_shape_gates()
    )
    stuck = await PostgresGoalStore(pg_pool).list_stuck(
        idle_days=0, alert_cooldown_days=0
    )
    assert len(stuck) == 1


async def test_priority_view_ranks_the_goal_with_no_failed_sources(pg_pool):
    goal_id = await make_goal_with_gates(
        pg_pool, status="awaiting_gate", gates=_dev_shape_gates()
    )
    view = PriorityView(
        PostgresLoopStore(pg_pool),
        PostgresGoalStore(pg_pool),
        PostgresHypothesisStore(pg_pool),
    )
    ranking = await view.rank()
    assert ranking.sources_failed == set()
    assert [i for i in ranking.items if i.source_kind == "goal"]
    assert any(str(goal_id) in str(i.source_id) for i in ranking.items)


async def test_stuck_goal_job_alerts_once_and_marks(pg_pool):
    goal_id = await make_goal_with_gates(
        pg_pool, status="awaiting_gate", gates=_dev_shape_gates()
    )
    notifier = AsyncMock()
    await StuckGoalJob(notifier, PostgresGoalStore(pg_pool)).run()
    assert notifier.push_notification.await_count == 1
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT last_stuck_alert_at FROM goals WHERE id = $1", goal_id
        )
