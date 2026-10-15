from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_agents.errors import ToolConfirmationRequired
from ze_agents.interrupt import workspace_confirmed
from ze_agents.types import Mode
from ze_automation.agents.goals.agent import GoalAgent
from ze_automation.agents.goals.tools import (
    abandon_goal,
    create_goal,
    pause_goal,
    resume_goal,
    steer_goal,
)
from ze_automation.goals.types import Goal, GoalStatus


def _store(goal: Goal | None = None) -> MagicMock:
    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.update_status = AsyncMock()
    store.list_active = AsyncMock(return_value=[])
    store.create_goal = AsyncMock()
    return store


def _goal() -> Goal:
    return Goal(
        title="Run a marathon",
        objective="o",
        success_condition="s",
        time_horizon="",
        type="custom",
        status=GoalStatus.ACTIVE,
    )


def test_goals_declares_read_first_and_read_is_autonomous():
    first = next(iter(GoalAgent.intents))
    assert first == "read"
    assert GoalAgent.intents["read"].mode == Mode.AUTONOMOUS


def test_goal_write_intents_keep_the_graph_gate_for_compound_turns():
    for name in ("create", "update", "delete"):
        assert GoalAgent.intents[name].mode == Mode.CONFIRM


async def test_abandon_asks_before_acting():
    store = _store(_goal())
    with pytest.raises(ToolConfirmationRequired) as exc:
        await abandon_goal(store, str(uuid4()))
    assert "Run a marathon" in exc.value.prompt
    store.update_status.assert_not_awaited()


async def test_pause_asks_before_acting():
    store = _store(_goal())
    with pytest.raises(ToolConfirmationRequired):
        await pause_goal(store, str(uuid4()))
    store.update_status.assert_not_awaited()


async def test_resume_asks_before_acting():
    paused = _goal()
    paused.status = GoalStatus.PAUSED
    store = _store(paused)
    executor = MagicMock()
    with pytest.raises(ToolConfirmationRequired):
        await resume_goal(store, executor, str(uuid4()))
    store.update_status.assert_not_awaited()


async def test_steer_asks_before_acting():
    executor = MagicMock()
    executor.steer = AsyncMock(return_value=True)
    with pytest.raises(ToolConfirmationRequired) as exc:
        await steer_goal(executor, str(uuid4()), "focus on interviews")
    assert "focus on interviews" in exc.value.prompt
    executor.steer.assert_not_awaited()


async def test_create_asks_before_any_store_access():
    store = _store()
    with pytest.raises(ToolConfirmationRequired) as exc:
        await create_goal(store, MagicMock(), MagicMock(), "Write a novel", "o", "s")
    assert "Write a novel" in exc.value.prompt
    store.list_active.assert_not_awaited()


async def test_confirmed_abandon_acts():
    store = _store(_goal())
    token = workspace_confirmed.set(True)
    try:
        result = await abandon_goal(store, str(uuid4()))
    finally:
        workspace_confirmed.reset(token)
    assert result["status"] == "abandoned"
    store.update_status.assert_awaited_once()


async def test_invalid_id_errors_without_asking():
    result = await abandon_goal(_store(), "not-a-uuid")
    assert "Invalid goal ID" in result["error"]
