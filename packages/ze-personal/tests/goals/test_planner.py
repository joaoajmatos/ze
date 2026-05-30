from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from ze_core.errors import GoalPlanError
from ze_personal.goals.planner import GoalPlanner
from ze_personal.goals.types import Goal, GoalStatus, MilestoneStatus, GateStatus


def _make_goal(**kwargs) -> Goal:
    defaults = dict(
        title="Run 15 discovery interviews",
        objective="Validate product hypothesis",
        success_condition="15 interviews completed",
        time_horizon="6 weeks",
    )
    return Goal(**{**defaults, **kwargs})


def _valid_plan_json(start_seq: int = 1) -> str:
    return json.dumps({
        "milestones": [
            {"title": "Research targets", "description": "Find 20 prospects", "sequence": start_seq, "intent": "read"},
            {"title": "Draft outreach", "description": "Write emails", "sequence": start_seq + 1, "intent": "create"},
            {"title": "Send outreach", "description": "Send to targets", "sequence": start_seq + 2, "intent": "execute"},
        ],
        "gates": [
            {"after_sequence": start_seq, "title": "Review target list"},
        ],
    })


@pytest.fixture
def client():
    m = AsyncMock()
    m.complete = AsyncMock(return_value=_valid_plan_json())
    return m


@pytest.fixture
def planner(client):
    return GoalPlanner(client=client, model="test-model")


async def test_plan_returns_milestones_and_gates(planner):
    goal = _make_goal()
    milestones, gates = await planner.plan(goal)

    assert len(milestones) == 3
    assert len(gates) == 1
    assert milestones[0].title == "Research targets"
    assert milestones[0].status == MilestoneStatus.PENDING
    assert gates[0].status == GateStatus.PENDING


async def test_plan_milestones_sorted_by_sequence(planner, client):
    # Return milestones out of order
    shuffled = json.dumps({
        "milestones": [
            {"title": "C", "description": "...", "sequence": 3, "intent": "read"},
            {"title": "A", "description": "...", "sequence": 1, "intent": "read"},
            {"title": "B", "description": "...", "sequence": 2, "intent": "read"},
        ],
        "gates": [{"after_sequence": 1, "title": "Check"}],
    })
    client.complete = AsyncMock(return_value=shuffled)
    milestones, _ = await planner.plan(_make_goal())
    assert [m.title for m in milestones] == ["A", "B", "C"]


async def test_plan_raises_on_empty_milestones(planner, client):
    client.complete = AsyncMock(return_value=json.dumps({"milestones": [], "gates": []}))
    with pytest.raises(GoalPlanError, match="No milestones"):
        await planner.plan(_make_goal())


async def test_plan_raises_on_no_gates(planner, client):
    client.complete = AsyncMock(return_value=json.dumps({
        "milestones": [{"title": "X", "description": "...", "sequence": 1, "intent": "read"}],
        "gates": [],
    }))
    with pytest.raises(GoalPlanError, match="verification gate"):
        await planner.plan(_make_goal())


async def test_plan_raises_on_invalid_json(planner, client):
    client.complete = AsyncMock(return_value="not json at all")
    with pytest.raises(GoalPlanError):
        await planner.plan(_make_goal())


async def test_replan_remaining_normalises_sequences(planner, client):
    client.complete = AsyncMock(return_value=json.dumps({
        "milestones": [
            {"title": "Follow up", "description": "...", "sequence": 1, "intent": "execute"},
        ],
        "gates": [{"after_sequence": 1, "title": "Check follow-ups"}],
    }))
    goal = _make_goal()
    milestones, gates = await planner.replan_remaining(goal, [], "pivot to warm leads", next_sequence=5)
    assert milestones[0].sequence == 5
    assert gates[0].after_sequence == 5


async def test_extract_learning_returns_string(planner, client):
    client.complete = AsyncMock(return_value="Targets prefer async outreach over cold calls.")
    result = await planner.extract_learning("Research targets", "Found 20 prospects on LinkedIn.")
    assert isinstance(result, str)
    assert len(result) > 0


async def test_plan_uses_learnings_in_prompt(planner, client):
    goal = _make_goal(learnings="Previous attempt revealed email bounces.")
    await planner.plan(goal)
    call_kwargs = client.complete.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    content = messages[0]["content"]
    assert "Previous attempt" in content
