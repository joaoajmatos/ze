from datetime import timedelta

import pytest
from ze_automation.goals.postgres import PostgresGoalStore

from tests.pg._builders import make_goal_with_gates, utcnow

pytestmark = pytest.mark.pg


async def _milestone(pool, goal_id, seq, status, completed_days_ago=None):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO goal_milestones
              (goal_id, title, description, sequence, status, completed_at)
            VALUES ($1, $2, 'd', $3, $4, $5)
            """,
            goal_id,
            f"Milestone {seq}",
            seq,
            status,
            utcnow() - timedelta(days=completed_days_ago) if completed_days_ago else None,
        )


async def test_progress_counts_next_milestone_and_open_gate(pg_pool):
    now = utcnow()
    goal_id = await make_goal_with_gates(
        pg_pool,
        status="awaiting_gate",
        gates=[("approved", now - timedelta(days=30), True), ("awaiting_approval", now - timedelta(days=9), False)],
    )
    await _milestone(pg_pool, goal_id, 1, "completed", 20)
    await _milestone(pg_pool, goal_id, 2, "skipped", 15)
    await _milestone(pg_pool, goal_id, 3, "pending")
    await _milestone(pg_pool, goal_id, 4, "pending")

    rows = await PostgresGoalStore(pg_pool).list_progress()
    [progress] = [r for r in rows if r.goal.id == goal_id]

    assert (progress.milestones_done, progress.milestones_total) == (2, 4)
    assert progress.next_milestone == "Milestone 3"
    assert progress.gate_title == "Gate 2"
    assert progress.gate_open_since is not None
    assert progress.stuck_since == progress.gate_open_since
    assert progress.last_progress_at is not None


async def test_active_goal_without_milestones_is_stuck_since_creation_when_old(pg_pool):
    goal_id = await make_goal_with_gates(pg_pool, status="active")
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE goals SET created_at = now() - interval '12 days' WHERE id = $1", goal_id)

    rows = await PostgresGoalStore(pg_pool).list_progress()
    [progress] = [r for r in rows if r.goal.id == goal_id]

    assert progress.milestones_total == 0 and progress.last_progress_at is None
    assert progress.stuck_since == progress.goal.created_at


async def test_completed_goals_are_not_listed(pg_pool):
    goal_id = await make_goal_with_gates(pg_pool, status="completed")
    rows = await PostgresGoalStore(pg_pool).list_progress()
    assert goal_id not in [r.goal.id for r in rows]
