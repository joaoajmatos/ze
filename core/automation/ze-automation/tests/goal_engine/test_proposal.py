from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_automation.goals.proposal import plan_for_goal, propose_goal
from ze_automation.goals.types import (
    Goal,
    GoalConvergence,
    GoalStatus,
    Milestone,
    VerificationGate,
)
from ze_automation.push_kinds import GOAL_PLAN_PROPOSED


def _goal(**kw) -> Goal:
    return Goal(
        title=kw.pop("title", "Learn Spanish"),
        objective="Reach conversational fluency in six months",
        success_condition="Hold a 20 minute conversation",
        status=GoalStatus.PLANNING,
        **kw,
    )


def _plan() -> tuple[list[Milestone], list[VerificationGate]]:
    milestones = [
        Milestone(goal_id=None, sequence=1, title="Pick a course", description="d"),
        Milestone(goal_id=None, sequence=2, title="Practise weekly", description="d"),
    ]
    gates = [VerificationGate(goal_id=None, after_sequence=1, title="Course chosen")]
    return milestones, gates


def _store() -> AsyncMock:
    store = AsyncMock()

    async def create_goal(goal: Goal) -> Goal:
        goal.id = uuid4()
        return goal

    store.create_goal = AsyncMock(side_effect=create_goal)
    return store


async def test_propose_goal_persists_the_plan_and_sends_the_proposal() -> None:
    store, notifier = _store(), AsyncMock()
    milestones, gates = _plan()

    goal = await propose_goal(
        store, AsyncMock(), notifier, _goal(), milestones, gates, active_goals=[]
    )

    assert goal is not None and goal.id is not None
    assert {m.goal_id for m in milestones} == {goal.id}
    assert gates[0].goal_id == goal.id
    assert store.create_milestone.await_count == 2
    store.create_gate.assert_awaited_once()
    args, kwargs = notifier.notify.await_args
    assert args[0] is GOAL_PLAN_PROPOSED
    assert [a.payload for a in kwargs["actions"]] == [
        f"goal_plan:yes:{goal.id}",
        f"goal_plan:no:{goal.id}",
    ]
    assert kwargs["target_type"] == "goal"
    assert kwargs["target_id"] == str(goal.id)


async def test_propose_goal_checks_convergence_against_active_goals() -> None:
    store, notifier, planner = _store(), AsyncMock(), AsyncMock()
    other = Goal(
        id=uuid4(),
        title="Travel",
        objective="o",
        success_condition="s",
        status=GoalStatus.ACTIVE,
    )
    planner.detect_convergence = AsyncMock(
        return_value=GoalConvergence(
            overlapping_goal_id=other.id,
            overlapping_goal_title="Travel",
            overlap_description="shared trip prep",
            suggestion="share outputs",
        )
    )
    milestones, gates = _plan()

    await propose_goal(
        store, planner, notifier, _goal(), milestones, gates, active_goals=[other]
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    planner.detect_convergence.assert_awaited_once()
    assert notifier.notify.await_count == 2


async def test_a_lost_claim_abandons_the_new_goal_and_sends_nothing() -> None:
    store, notifier = _store(), AsyncMock()
    milestones, gates = _plan()
    claim = AsyncMock(return_value=False)

    result = await propose_goal(
        store,
        AsyncMock(),
        notifier,
        _goal(),
        milestones,
        gates,
        active_goals=[],
        claim=claim,
    )

    assert result is None
    claim.assert_awaited_once()
    created = claim.await_args.args[0]
    store.update_status.assert_awaited_once_with(created.id, GoalStatus.ABANDONED)
    store.create_milestone.assert_not_called()
    store.create_gate.assert_not_called()
    notifier.notify.assert_not_called()


async def test_a_won_claim_gets_the_created_goal_and_the_proposal_goes_out() -> None:
    store, notifier = _store(), AsyncMock()
    milestones, gates = _plan()
    claim = AsyncMock(return_value=True)

    goal = await propose_goal(
        store,
        AsyncMock(),
        notifier,
        _goal(),
        milestones,
        gates,
        active_goals=[],
        claim=claim,
    )

    assert goal is not None
    claim.assert_awaited_once_with(goal)
    notifier.notify.assert_awaited_once()


async def test_plan_for_goal_passes_recent_milestone_output_to_the_planner() -> None:
    store, planner = AsyncMock(), AsyncMock()
    prior = [object()]
    store.list_completed_milestone_summaries = AsyncMock(return_value=prior)
    planned = _plan()
    planner.plan = AsyncMock(return_value=planned)
    goal = _goal()

    result = await plan_for_goal(store, planner, goal)

    assert result == planned
    planner.plan.assert_awaited_once_with(goal, prior_work=prior)


async def test_plan_for_goal_plans_without_prior_work_when_the_query_fails() -> None:
    store, planner = AsyncMock(), AsyncMock()
    store.list_completed_milestone_summaries = AsyncMock(side_effect=RuntimeError("db"))
    planner.plan = AsyncMock(return_value=_plan())
    goal = _goal()

    await plan_for_goal(store, planner, goal)

    planner.plan.assert_awaited_once_with(goal, prior_work=None)


async def test_a_failed_milestone_write_abandons_the_goal_and_releases_the_claim() -> (
    None
):
    store, notifier = _store(), AsyncMock()
    store.create_milestone = AsyncMock(side_effect=RuntimeError("db down"))
    milestones, gates = _plan()
    release = AsyncMock()

    with pytest.raises(RuntimeError, match="db down"):
        await propose_goal(
            store,
            AsyncMock(),
            notifier,
            _goal(),
            milestones,
            gates,
            active_goals=[],
            claim=AsyncMock(return_value=True),
            release=release,
        )

    created = store.create_goal.await_args.args[0]
    store.update_status.assert_awaited_once_with(created.id, GoalStatus.ABANDONED)
    release.assert_awaited_once_with(created)
    notifier.notify.assert_not_called()


async def test_a_failed_gate_write_gets_the_same_cleanup() -> None:
    store = _store()
    store.create_gate = AsyncMock(side_effect=RuntimeError("db down"))
    milestones, gates = _plan()
    release = AsyncMock()

    with pytest.raises(RuntimeError):
        await propose_goal(
            store,
            AsyncMock(),
            AsyncMock(),
            _goal(),
            milestones,
            gates,
            active_goals=[],
            claim=AsyncMock(return_value=True),
            release=release,
        )

    store.update_status.assert_awaited_once()
    release.assert_awaited_once()


async def test_a_failed_proposal_push_gets_the_same_cleanup() -> None:
    store, notifier = _store(), AsyncMock()
    notifier.notify = AsyncMock(side_effect=RuntimeError("push down"))
    milestones, gates = _plan()
    release = AsyncMock()

    with pytest.raises(RuntimeError, match="push down"):
        await propose_goal(
            store,
            AsyncMock(),
            notifier,
            _goal(),
            milestones,
            gates,
            active_goals=[],
            release=release,
        )

    store.update_status.assert_awaited_once()
    release.assert_awaited_once()


async def test_a_failing_cleanup_does_not_mask_the_original_error() -> None:
    store = _store()
    store.create_milestone = AsyncMock(side_effect=RuntimeError("db down"))
    store.update_status = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    release = AsyncMock(side_effect=RuntimeError("release failed"))
    milestones, gates = _plan()

    with pytest.raises(RuntimeError, match="db down"):
        await propose_goal(
            store,
            AsyncMock(),
            AsyncMock(),
            _goal(),
            milestones,
            gates,
            active_goals=[],
            release=release,
        )

    release.assert_awaited_once()
