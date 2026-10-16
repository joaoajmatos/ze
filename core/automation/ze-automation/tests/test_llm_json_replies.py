"""Planner sites parse JSON from fenced and prose-wrapped LLM replies."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_agents.errors import GoalPlanError, WorkflowPlanError
from ze_automation.goals.planner import GoalPlanner
from ze_automation.goals.types import Goal, GoalStatus
from ze_automation.workflow.planner import WorkflowPlanner
from ze_automation.workflow.types import StepResult

WRAPS = [
    pytest.param(lambda s: s, id="bare"),
    pytest.param(lambda s: f"```json\n{s}\n```", id="fenced"),
    pytest.param(lambda s: f"Here you go:\n```json\n{s}\n```\nCheers.", id="prose"),
    pytest.param(lambda s: f"Result: {s} (done)", id="inline-prose"),
]


def _goal() -> Goal:
    return Goal(
        id=uuid4(),
        title="Launch",
        objective="Ship an MVP",
        success_condition="First customer",
        status=GoalStatus.ACTIVE,
    )


def _goal_planner(reply: str) -> GoalPlanner:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=reply)
    return GoalPlanner(client=client, model="m")


def _workflow_planner(reply: str) -> WorkflowPlanner:
    client = MagicMock()
    client.complete = AsyncMock(return_value=reply)
    return WorkflowPlanner(openrouter_client=client)


@pytest.mark.parametrize("wrap", WRAPS)
async def test_goal_plan(wrap):
    plan = {
        "milestones": [
            {"title": "T", "description": "D", "sequence": 1, "intent": "read"}
        ],
        "gates": [{"after_sequence": 1, "title": "G"}],
    }
    milestones, _ = await _goal_planner(wrap(json.dumps(plan))).plan(_goal())
    assert [m.title for m in milestones] == ["T"]


async def test_goal_plan_unparseable_raises_goal_plan_error():
    with pytest.raises(GoalPlanError):
        await _goal_planner("sorry, no plan").plan(_goal())


@pytest.mark.parametrize("wrap", WRAPS)
async def test_goal_extract_procedure(wrap):
    from ze_automation.goals.types import Milestone, MilestoneStatus

    m = Milestone(
        goal_id=uuid4(),
        title="T",
        description="D",
        sequence=1,
        status=MilestoneStatus.COMPLETED,
    )
    reply = wrap(json.dumps({"name": "Proc", "trigger": "t", "steps": ["a"]}))
    proc = await _goal_planner(reply).extract_procedure(_goal(), [m])
    assert proc is not None and proc.name == "Proc"


@pytest.mark.parametrize("wrap", WRAPS)
async def test_goal_detect_convergence(wrap):
    other = _goal()
    reply = wrap(
        json.dumps(
            {
                "overlapping_goal_id": str(other.id),
                "overlapping_goal_title": other.title,
                "overlap_description": "same",
                "suggestion": "share",
            }
        )
    )
    result = await _goal_planner(reply).detect_convergence(_goal(), [other])
    assert result is not None and result.overlapping_goal_id == other.id


@pytest.mark.parametrize("wrap", WRAPS)
async def test_workflow_plan(wrap):
    reply = wrap(json.dumps([{"task": "Send", "agent_hint": None, "intent": "create"}]))
    steps = await _workflow_planner(reply).plan("do it")
    assert steps[0].task == "Send"


async def test_workflow_plan_unparseable_raises_plan_error():
    with pytest.raises(WorkflowPlanError):
        await _workflow_planner("I cannot").plan("do it")


@pytest.mark.parametrize("wrap", WRAPS)
async def test_workflow_extract_schedule(wrap):
    reply = wrap(json.dumps({"cron": "0 8 * * 1"}))
    assert await _workflow_planner(reply).extract_schedule("mondays") == "0 8 * * 1"


@pytest.mark.parametrize("wrap", WRAPS)
async def test_workflow_extract_procedure(wrap):
    reply = wrap(json.dumps({"name": "P", "trigger": "t"}))
    done = [
        StepResult(
            step_index=0, task="a", output="ok", success=True, error=None, duration_ms=0
        )
    ]
    proc = await _workflow_planner(reply).extract_procedure("wf", done)
    assert proc is not None and proc.name == "P"
