"""Integration-style tests for gate approve/stop/redirect and plan approval."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ze.errors import GoalPlanError
from ze_core.goals.executor import GoalExecutor
from ze_core.goals.types import (
    Goal,
    GoalStatus,
    GateStatus,
    Milestone,
    MilestoneStatus,
    VerificationGate,
)
from tests.goals.test_executor import make_executor, make_gate, make_goal, make_milestone


async def test_handle_gate_redirected_replaces_milestones_and_gates():
    goal = make_goal(status=GoalStatus.AWAITING_GATE)
    m1 = make_milestone(1, MilestoneStatus.COMPLETED, goal_id=goal.id, output="found 5")
    gate = make_gate(1, GateStatus.AWAITING_APPROVAL, goal_id=goal.id)

    new_m = Milestone(
        id=uuid4(),
        goal_id=goal.id,
        title="New step",
        description="Do new step",
        sequence=2,
    )
    new_g = VerificationGate(
        id=uuid4(),
        goal_id=goal.id,
        after_sequence=2,
        title="New checkpoint",
    )

    store = MagicMock()
    store.get_gate = AsyncMock(return_value=gate)
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(return_value=[m1])
    store.add_learning = AsyncMock()
    store.append_learnings = AsyncMock()
    store.replace_pending_milestones = AsyncMock(return_value=[new_m])
    store.replace_pending_gates = AsyncMock(return_value=[new_g])
    store.resolve_gate = AsyncMock()
    store.update_status = AsyncMock()

    planner = MagicMock()
    planner.replan_remaining = AsyncMock(return_value=([new_m], [new_g]))

    executor = make_executor(goal_store=store, goal_planner=planner)
    advance_calls = []
    orig = executor._advance_unlocked

    async def track(gid):
        advance_calls.append(gid)
        await orig(gid)

    with patch.object(executor, "_advance_unlocked", side_effect=track):
        store.get_goal = AsyncMock(return_value=make_goal(status=GoalStatus.ACTIVE))
        store.list_milestones = AsyncMock(return_value=[])
        await executor.handle_gate_redirected(gate.id, "Focus on Spain")

    store.replace_pending_milestones.assert_awaited_once()
    store.replace_pending_gates.assert_awaited_once()
    store.resolve_gate.assert_awaited_once_with(
        gate.id, GateStatus.REDIRECTED, user_feedback="Focus on Spain",
    )
    store.update_status.assert_awaited_with(goal.id, GoalStatus.ACTIVE)


async def test_handle_gate_redirected_skips_when_replan_fails():
    goal = make_goal()
    gate = make_gate(1, GateStatus.AWAITING_APPROVAL, goal_id=goal.id)

    store = MagicMock()
    store.get_gate = AsyncMock(return_value=gate)
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(return_value=[])
    store.add_learning = AsyncMock()
    store.append_learnings = AsyncMock()

    planner = MagicMock()
    planner.replan_remaining = AsyncMock(side_effect=GoalPlanError("bad plan"))

    push = AsyncMock()
    executor = make_executor(goal_store=store, goal_planner=planner, push=push)

    await executor.handle_gate_redirected(gate.id, "change course")
    store.replace_pending_milestones.assert_not_called()
    push.assert_awaited()


async def test_approve_plan_activates_and_advances():
    goal_id = uuid4()
    goal = make_goal(id=goal_id, status=GoalStatus.PLANNING)

    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.update_status = AsyncMock()

    executor = make_executor(goal_store=store)
    with patch.object(executor, "advance", new_callable=AsyncMock) as mock_advance:
        ok = await executor.approve_plan(goal_id)
        assert ok is True
        store.update_status.assert_awaited_once_with(goal_id, GoalStatus.ACTIVE)
        await asyncio.sleep(0)
        mock_advance.assert_awaited_once_with(goal_id)


async def test_approve_plan_returns_false_when_not_planning():
    goal = make_goal(status=GoalStatus.ACTIVE)
    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.update_status = AsyncMock()
    executor = make_executor(goal_store=store)
    assert await executor.approve_plan(goal.id) is False
    store.update_status.assert_not_called()


async def test_reject_plan_abandons_goal():
    goal = make_goal(status=GoalStatus.PLANNING)
    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.update_status = AsyncMock()
    executor = make_executor(goal_store=store)
    assert await executor.reject_plan(goal.id) is True
    store.update_status.assert_awaited_once_with(goal.id, GoalStatus.ABANDONED)
