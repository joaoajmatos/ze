from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_core.errors import GoalPlanError
from ze_personal.goals.planner import GoalPlanner, _parse_plan
from ze_personal.goals.types import Goal, GoalStatus, Milestone, PriorMilestoneOutput


def _goal() -> Goal:
    return Goal(
        id=uuid4(),
        title="Launch a SaaS product",
        objective="Build and launch an MVP",
        success_condition="First paying customer",
        status=GoalStatus.ACTIVE,
    )


def _prior(
    *,
    goal_title="Market Research Goal",
    milestone_title="Survey SaaS competitors",
    output_snippet="Found 12 competitors in the space.",
    completed_days_ago=7,
) -> PriorMilestoneOutput:
    return PriorMilestoneOutput(
        goal_id=uuid4(),
        goal_title=goal_title,
        milestone_id=uuid4(),
        milestone_title=milestone_title,
        output_snippet=output_snippet,
        completed_days_ago=completed_days_ago,
    )


def _plan_json(reuse_hint: str = "") -> str:
    return json.dumps({
        "milestones": [
            {
                "title": "Research market",
                "description": "Survey the market landscape.",
                "agent_hint": "research",
                "intent": "read",
                "sequence": 1,
                "reuse_hint": reuse_hint,
            }
        ],
        "gates": [
            {"after_sequence": 1, "title": "Review research"}
        ],
    })


def _make_planner(response: str) -> GoalPlanner:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=response)
    return GoalPlanner(client=client, model="test-model")


# ── _parse_plan ───────────────────────────────────────────────────────────────

def test_parse_plan_reads_reuse_hint():
    milestones, _ = _parse_plan(_plan_json(reuse_hint="Prior goal 'X' did this 5 days ago."), uuid4())
    assert milestones[0].reuse_hint == "Prior goal 'X' did this 5 days ago."


def test_parse_plan_defaults_reuse_hint_to_empty_when_absent():
    raw = json.dumps({
        "milestones": [
            {"title": "Step", "description": "Do it", "sequence": 1}
        ],
        "gates": [{"after_sequence": 1, "title": "Check"}],
    })
    milestones, _ = _parse_plan(raw, uuid4())
    assert milestones[0].reuse_hint == ""


def test_parse_plan_truncates_reuse_hint_at_300_chars():
    long_hint = "x" * 500
    milestones, _ = _parse_plan(_plan_json(reuse_hint=long_hint), uuid4())
    assert len(milestones[0].reuse_hint) == 300


def test_parse_plan_handles_null_reuse_hint():
    raw = json.dumps({
        "milestones": [
            {"title": "Step", "description": "Do it", "sequence": 1, "reuse_hint": None}
        ],
        "gates": [{"after_sequence": 1, "title": "Check"}],
    })
    milestones, _ = _parse_plan(raw, uuid4())
    assert milestones[0].reuse_hint == ""


# ── GoalPlanner.plan() ────────────────────────────────────────────────────────

async def test_plan_with_empty_prior_work_sends_unchanged_prompt():
    planner = _make_planner(_plan_json())
    goal = _goal()

    await planner.plan(goal, prior_work=[])

    prompt = planner._client.complete.call_args.kwargs["messages"][0]["content"]
    assert "PRIOR WORK" not in prompt


async def test_plan_with_none_prior_work_sends_unchanged_prompt():
    planner = _make_planner(_plan_json())
    goal = _goal()

    await planner.plan(goal, prior_work=None)

    prompt = planner._client.complete.call_args.kwargs["messages"][0]["content"]
    assert "PRIOR WORK" not in prompt


async def test_plan_with_prior_work_appends_prior_work_block():
    planner = _make_planner(_plan_json())
    goal = _goal()
    pw = _prior()

    await planner.plan(goal, prior_work=[pw])

    prompt = planner._client.complete.call_args.kwargs["messages"][0]["content"]
    assert "PRIOR WORK FROM OTHER GOALS" in prompt
    assert pw.goal_title in prompt
    assert pw.milestone_title in prompt
    assert pw.output_snippet in prompt
    assert f"{pw.completed_days_ago}d ago" in prompt


async def test_plan_returns_milestones_with_reuse_hint():
    hint = "Prior goal 'Market Research' already produced competitor list (7 days ago)."
    planner = _make_planner(_plan_json(reuse_hint=hint))
    goal = _goal()

    milestones, _ = await planner.plan(goal, prior_work=[_prior()])

    assert milestones[0].reuse_hint == hint


# ── GoalPlanner.replan_remaining() ───────────────────────────────────────────

async def test_replan_with_prior_work_appends_prior_work_block():
    planner = _make_planner(_plan_json())
    goal = _goal()
    completed = [
        Milestone(
            id=uuid4(), goal_id=goal.id, title="Done step", description="d",
            sequence=1, status=__import__("ze_personal.goals.types", fromlist=["MilestoneStatus"]).MilestoneStatus.COMPLETED,
            output="Some output",
        )
    ]
    pw = _prior()

    await planner.replan_remaining(goal, completed, "New direction", next_sequence=2, prior_work=[pw])

    prompt = planner._client.complete.call_args.kwargs["messages"][0]["content"]
    assert "PRIOR WORK FROM OTHER GOALS" in prompt
    assert pw.goal_title in prompt


async def test_replan_with_empty_prior_work_omits_prior_work_block():
    planner = _make_planner(_plan_json())
    goal = _goal()

    await planner.replan_remaining(goal, [], "New direction", next_sequence=1, prior_work=[])

    prompt = planner._client.complete.call_args.kwargs["messages"][0]["content"]
    assert "PRIOR WORK" not in prompt
