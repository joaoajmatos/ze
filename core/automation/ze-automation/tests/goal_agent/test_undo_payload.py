"""Undo payload for create_goal (Phase 180)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.errors import GoalPlanError
from ze_automation.agents.goals.agent import GoalAgent
from ze_automation.agents.goals.tools import create_goal
from ze_automation.goals.types import Goal


def _store(goal_id):
    store = AsyncMock()
    store.list_active = AsyncMock(return_value=[])
    store.list_completed_milestone_summaries = AsyncMock(return_value=[])

    async def _create(goal: Goal) -> Goal:
        goal.id = goal_id
        return goal

    store.create_goal = AsyncMock(side_effect=_create)
    return store


async def _call(store, planner):
    return await create_goal(
        store=store,
        planner=planner,
        notifier=AsyncMock(),
        goal_title="Learn Rust",
        objective="Ship a CLI",
        success_condition="CLI published",
    )


async def test_create_goal_returns_undo_payload_on_success(goal_writes_confirmed):
    gid = uuid4()
    planner = AsyncMock()
    planner.plan = AsyncMock(return_value=([], []))
    result = await _call(_store(gid), planner)
    assert result["undo"] == {"goal_id": str(gid)}
    assert result["id"] == str(gid)


async def test_create_goal_no_payload_on_planner_error(goal_writes_confirmed):
    planner = AsyncMock()
    planner.plan = AsyncMock(side_effect=GoalPlanError("bad plan"))
    store = _store(uuid4())
    result = await _call(store, planner)
    assert "error" in result
    assert "undo" not in result
    store.create_goal.assert_not_awaited()


def test_tool_deps_has_the_keys_the_loop_used():
    store, planner, executor, notifier = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    agent = GoalAgent(
        openrouter_client=AsyncMock(),
        goal_store=store,
        goal_planner=planner,
        goal_executor=executor,
        notifier=notifier,
    )
    assert agent.tool_deps() == {
        "store": store,
        "planner": planner,
        "executor": executor,
        "notifier": notifier,
    }
