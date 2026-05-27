import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ze_core.errors import GoalExecutionError
from ze_core.goals.executor import GoalExecutor
from ze_core.interface.types import Notification
from ze.goals.types import (
    Goal,
    GoalLearning,
    GoalStatus,
    GateStatus,
    Milestone,
    MilestoneStatus,
    VerificationGate,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_goal(**overrides) -> Goal:
    defaults = dict(
        id=uuid4(),
        title="My Goal",
        objective="obj",
        success_condition="done",
        status=GoalStatus.ACTIVE,
    )
    defaults.update(overrides)
    return Goal(**defaults)


def make_milestone(sequence: int, status: MilestoneStatus = MilestoneStatus.PENDING, **overrides) -> Milestone:
    goal_id = overrides.pop("goal_id", uuid4())
    return Milestone(
        id=uuid4(),
        goal_id=goal_id,
        title=f"Step {sequence}",
        description=f"Do step {sequence}",
        sequence=sequence,
        status=status,
        **overrides,
    )


def make_gate(after_sequence: int, status: GateStatus = GateStatus.PENDING, **overrides) -> VerificationGate:
    goal_id = overrides.pop("goal_id", uuid4())
    return VerificationGate(
        id=uuid4(),
        goal_id=goal_id,
        after_sequence=after_sequence,
        title=f"Gate after {after_sequence}",
        status=status,
        **overrides,
    )


def make_executor(goal_store=None, goal_planner=None, push=None, agent_getter=None):
    if goal_store is None:
        goal_store = MagicMock()
        goal_store.get_goal = AsyncMock(return_value=None)
        goal_store.list_milestones = AsyncMock(return_value=[])
        goal_store.get_pending_gate = AsyncMock(return_value=None)
        goal_store.update_status = AsyncMock()
        goal_store.update_milestone = AsyncMock()
        goal_store.add_learning = AsyncMock()
        goal_store.append_learnings = AsyncMock()
        goal_store.fire_gate = AsyncMock()
        goal_store.get_gate = AsyncMock(return_value=None)
        goal_store.resolve_gate = AsyncMock()
        goal_store.replace_pending_milestones = AsyncMock(return_value=[])
        goal_store.replace_pending_gates = AsyncMock(return_value=[])
        goal_store.create_gate = AsyncMock()

    if goal_planner is None:
        goal_planner = MagicMock()
        goal_planner.extract_learning = AsyncMock(return_value="A useful insight.")
        goal_planner.replan_remaining = AsyncMock(return_value=([], []))

    if push is None:
        push = AsyncMock()

    if agent_getter is None:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=MagicMock(response="Done."))
        agent_getter = lambda name: mock_agent

    return GoalExecutor(
        goal_store=goal_store,
        goal_planner=goal_planner,
        push=push,
        agent_getter=agent_getter,
    )


# ── advance: non-active goal ──────────────────────────────────────────────────

async def test_advance_returns_early_if_goal_not_active():
    store = MagicMock()
    store.get_goal = AsyncMock(return_value=make_goal(status=GoalStatus.PAUSED))
    store.list_milestones = AsyncMock(return_value=[])
    executor = make_executor(goal_store=store)
    await executor.advance(uuid4())
    store.list_milestones.assert_not_called()


async def test_advance_resets_stuck_in_progress_milestone():
    goal = make_goal()
    stuck = make_milestone(1, MilestoneStatus.IN_PROGRESS, goal_id=goal.id)
    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(side_effect=[
        [stuck],
        [make_milestone(1, MilestoneStatus.PENDING, goal_id=goal.id)],
    ])
    store.get_pending_gate = AsyncMock(return_value=None)
    store.update_milestone = AsyncMock()

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=MagicMock(response="ok"))

    executor = make_executor(goal_store=store, agent_getter=lambda _: mock_agent)

    with patch("ze_core.goals.executor.asyncio.create_task"):
        await executor.advance(goal.id)

    store.update_milestone.assert_any_call(stuck.id, MilestoneStatus.PENDING)


async def test_advance_marks_completed_when_no_pending_milestones():
    goal = make_goal()
    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(return_value=[
        make_milestone(1, MilestoneStatus.COMPLETED, goal_id=goal.id),
    ])
    store.get_pending_gate = AsyncMock(return_value=None)
    store.update_status = AsyncMock()
    push = AsyncMock()
    executor = make_executor(goal_store=store, push=push)
    await executor.advance(goal.id)
    store.update_status.assert_awaited_once_with(goal.id, GoalStatus.COMPLETED)
    push.assert_awaited_once()
    assert isinstance(push.call_args.args[0], Notification)


async def test_advance_fires_gate_when_due():
    goal = make_goal()
    m1 = make_milestone(1, MilestoneStatus.COMPLETED, goal_id=goal.id, output="done")
    m2 = make_milestone(2, MilestoneStatus.PENDING, goal_id=goal.id)
    gate = make_gate(1, GateStatus.PENDING, goal_id=goal.id)

    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(return_value=[m1, m2])
    store.get_pending_gate = AsyncMock(return_value=gate)
    store.fire_gate = AsyncMock()
    store.update_status = AsyncMock()
    push = AsyncMock()

    executor = make_executor(goal_store=store, push=push)
    await executor.advance(goal.id)

    store.fire_gate.assert_awaited_once()
    store.update_status.assert_awaited_once_with(goal.id, GoalStatus.AWAITING_GATE)
    notif = push.call_args.args[0]
    assert isinstance(notif, Notification)
    assert len(notif.actions) == 3


async def test_advance_executes_pending_milestone():
    goal = make_goal()
    m1 = make_milestone(1, MilestoneStatus.PENDING, goal_id=goal.id)

    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(return_value=[m1])
    store.get_pending_gate = AsyncMock(return_value=None)
    store.update_milestone = AsyncMock()
    store.add_learning = AsyncMock()
    store.append_learnings = AsyncMock()
    push = AsyncMock()

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=MagicMock(response="Done."))

    executor = make_executor(goal_store=store, push=push, agent_getter=lambda _: mock_agent)

    with patch("ze_core.goals.executor.asyncio.create_task"):
        call_count = 0
        orig_unlocked = executor._advance_unlocked

        async def limited_unlocked(gid):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return
            await orig_unlocked(gid)

        executor._advance_unlocked = limited_unlocked
        await executor.advance(goal.id)

    store.update_milestone.assert_awaited()
    push.assert_awaited()


async def test_advance_skips_milestone_on_execution_error():
    goal = make_goal()
    m1 = make_milestone(1, MilestoneStatus.PENDING, goal_id=goal.id)

    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(return_value=[m1])
    store.get_pending_gate = AsyncMock(return_value=None)
    store.update_milestone = AsyncMock()
    store.add_learning = AsyncMock()

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(side_effect=Exception("network error"))

    executor = make_executor(goal_store=store, agent_getter=lambda _: mock_agent)

    with patch("ze_core.goals.executor.asyncio.create_task"):
        await executor.advance(goal.id)

    store.update_milestone.assert_any_call(
        m1.id, MilestoneStatus.SKIPPED, output=pytest.approx("Failed: Milestone 1 (Step 1) failed: network error", abs=100)
    )


async def test_approve_plan_activates_goal():
    goal = make_goal(status=GoalStatus.PLANNING)
    store = MagicMock()
    store.get_goal = AsyncMock(return_value=goal)
    store.update_status = AsyncMock()
    executor = make_executor(goal_store=store)

    with patch("ze_core.goals.executor.asyncio.create_task"):
        result = await executor.approve_plan(goal.id)

    assert result is True
    store.update_status.assert_awaited_once_with(goal.id, GoalStatus.ACTIVE)


async def test_handle_gate_redirected_replans():
    goal = make_goal()
    gate = make_gate(1, GateStatus.AWAITING_APPROVAL, goal_id=goal.id)
    m1 = make_milestone(1, MilestoneStatus.COMPLETED, goal_id=goal.id)

    store = MagicMock()
    store.get_gate = AsyncMock(return_value=gate)
    store.get_goal = AsyncMock(return_value=goal)
    store.list_milestones = AsyncMock(return_value=[m1])
    store.add_learning = AsyncMock()
    store.append_learnings = AsyncMock()
    store.replace_pending_milestones = AsyncMock(return_value=[])
    store.replace_pending_gates = AsyncMock(return_value=[])
    store.resolve_gate = AsyncMock()
    store.update_status = AsyncMock()

    new_m = make_milestone(2, goal_id=goal.id)
    planner = MagicMock()
    planner.replan_remaining = AsyncMock(return_value=([new_m], []))

    executor = make_executor(goal_store=store, goal_planner=planner)

    with patch("ze_core.goals.executor.asyncio.create_task"):
        await executor.handle_gate_redirected(gate.id, "focus on Portugal only")

    planner.replan_remaining.assert_awaited_once()
    store.resolve_gate.assert_awaited_once_with(gate.id, GateStatus.REDIRECTED, user_feedback="focus on Portugal only")
