"""Plan-time pre-approval of asks-first tools (Phase 181, US5, FR-023/FR-024)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import ze_automation.agents.goals.tools as goal_tools
import ze_automation.agents.workflow.tools as wf_tools
from ze_agents.base_agent import BaseAgent
from ze_agents.park import current_approval
import ze_agents.registry as registry_mod
import ze_agents.tool as tool_mod
from ze_agents.registry import agent
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, tool
from ze_automation.goals.types import Goal, Milestone
from ze_automation.holds.planned import (
    plan_writes_check,
    planned_writes,
    writes_needing_approval,
)
from ze_automation.workflow.types import Workflow, WorkflowStep


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    monkeypatch.setattr(registry_mod, "_registry", dict(registry_mod._registry))
    monkeypatch.setattr(tool_mod, "_tools", dict(tool_mod._tools))

    async def plan_send_email(to: str = "") -> str:
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
    )(plan_send_email)

    async def plan_archive_email(id: str = "") -> str:
        return "archived"

    tool(
        access=ToolAccess.WRITE,
        description="archive",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="archived an email",
    )(plan_archive_email)

    async def plan_list_mail() -> str:
        return "mail"

    tool(access=ToolAccess.READ, description="list")(plan_list_mail)

    async def plan_ingest(text: str = "") -> str:
        return "saved"

    tool(
        access=ToolAccess.WRITE,
        description="plan_ingest",
        reversibility=ToolReversibility.IRREVERSIBLE,
        asks_first=False,
        no_ask_reason="saves what the user asked to save",
        effect_phrase="ingested text",
    )(plan_ingest)

    cls = type(
        "_Messenger",
        (BaseAgent,),
        {
            "name": "plan_messenger",
            "description": "mail",
            "tools": [
                "plan_list_mail",
                "plan_send_email",
                "plan_archive_email",
                "plan_ingest",
            ],
        },
    )
    agent(cls)
    reader = type(
        "_Research",
        (BaseAgent,),
        {"name": "plan_research", "description": "r", "tools": ["plan_list_mail"]},
    )
    agent(reader)
    yield


def _step(id_: str, hint: str | None, task: str = "t", **kw) -> WorkflowStep:
    return WorkflowStep(task=task, agent_hint=hint, id=id_, **kw)


def test_planned_writes_lists_the_asks_first_tools_of_the_hinted_agent() -> None:
    assert planned_writes(_step("s0", "plan_messenger")) == [
        "plan_send_email",
        "plan_archive_email",
    ]
    assert planned_writes(_step("s0", "plan_research")) == []


def test_planned_writes_is_empty_without_a_hint_or_for_an_unknown_agent() -> None:
    assert planned_writes(_step("s0", None)) == []
    assert planned_writes(_step("s0", "email")) == []


def test_plan_check_asks_with_the_effects_per_step() -> None:
    steps = [_step("s0", "plan_research"), _step("s1", "plan_messenger")]
    decision = plan_writes_check(steps)
    assert decision.kind == "ask"
    assert decision.reason == (
        "Step 2 (plan_messenger) may: send an email, archive an email"
    )


def test_plan_check_runs_when_no_step_plans_a_write() -> None:
    assert (
        plan_writes_check([_step("s0", "plan_research"), _step("s1", None)]).kind
        == "run"
    )


def test_plan_check_uses_the_given_label() -> None:
    milestone = Milestone(
        goal_id=uuid4(),
        title="m",
        description="",
        sequence=3,
        agent_hint="plan_messenger",
    )
    decision = plan_writes_check([milestone], label="Milestone")
    assert decision.reason.startswith("Milestone 1 (plan_messenger) may:")


def test_writes_needing_approval_names_step_agent_and_tools() -> None:
    steps = [_step("s0", "plan_research"), _step("s1", "plan_messenger")]
    assert writes_needing_approval(steps) == [
        {
            "step_id": "s1",
            "agent": "plan_messenger",
            "tools": ["plan_send_email", "plan_archive_email"],
        }
    ]


def _workflow(steps: list[WorkflowStep]) -> Workflow:
    now = datetime.now(tz=timezone.utc)
    return Workflow(
        id=uuid4(),
        name="weekly",
        description="d",
        steps=steps,
        schedule=None,
        enabled=True,
        last_run_at=None,
        next_run_at=None,
        created_at=now,
        updated_at=now,
    )


async def _create(planner, store, approval) -> dict:
    token = current_approval.set(approval)
    try:
        return await wf_tools.create_workflow(
            store=store,
            planner=planner,
            scheduler=AsyncMock(),
            workflow_name="weekly",
            description="email me my week",
        )
    finally:
        current_approval.reset(token)


def _planner(steps: list[WorkflowStep]):
    from ze_automation.workflow.planner import WorkflowPlanner

    planner = WorkflowPlanner(openrouter_client=MagicMock())
    planner.plan = AsyncMock(return_value=steps)  # type: ignore[method-assign]
    planner.extract_schedule = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return planner


async def test_create_workflow_check_asks_listing_the_planned_writes() -> None:
    planner = _planner([_step("s0", "plan_research"), _step("s1", "plan_messenger")])
    args = {
        "planner": planner,
        "workflow_name": "weekly",
        "description": "email me my week",
    }
    decision = await wf_tools.create_workflow_check(args, MagicMock())
    assert decision.kind == "ask"
    assert "Step 2 (plan_messenger) may: send an email" in decision.reason


async def test_create_workflow_check_runs_when_the_plan_writes_nothing() -> None:
    planner = _planner([_step("s0", "plan_research")])
    args = {"planner": planner, "workflow_name": "w", "description": "d"}
    assert (await wf_tools.create_workflow_check(args, MagicMock())).kind == "run"


async def test_approving_create_workflow_stores_approved_writes_on_the_steps() -> None:
    planner = _planner([_step("s0", "plan_research"), _step("s1", "plan_messenger")])
    store = AsyncMock()
    store.create = AsyncMock(return_value=uuid4())
    await wf_tools.create_workflow_check(
        {
            "planner": planner,
            "workflow_name": "weekly",
            "description": "email me my week",
        },
        MagicMock(),
    )
    await _create(planner, store, {"request_id": "r1", "outcome": "approved"})
    saved = store.create.await_args.args[0]
    assert [s.approved_writes for s in saved.steps] == [
        [],
        ["plan_send_email", "plan_archive_email"],
    ]
    assert planner.plan.await_count == 1


async def test_create_workflow_without_approval_grants_nothing() -> None:
    planner = _planner([_step("s1", "plan_messenger")])
    store = AsyncMock()
    store.create = AsyncMock(return_value=uuid4())
    await _create(planner, store, None)
    saved = store.create.await_args.args[0]
    assert saved.steps[0].approved_writes == []


async def test_approval_after_the_plan_memo_is_gone_grants_nothing() -> None:
    """A re-plan may differ from what the user saw, so nothing is granted."""
    planner = _planner([_step("s1", "plan_messenger")])
    store = AsyncMock()
    store.create = AsyncMock(return_value=uuid4())
    await _create(planner, store, {"request_id": "r1", "outcome": "approved"})
    assert store.create.await_args.args[0].steps[0].approved_writes == []


def _steps_json(*steps: dict) -> str:
    return json.dumps(list(steps))


def _item(id_: str, hint: str, task: str = "t") -> dict:
    return {"id": id_, "task": task, "agent_hint": hint}


async def test_edit_steps_check_always_asks_and_lists_planned_writes() -> None:
    store = AsyncMock()
    store.get_by_name = AsyncMock(
        return_value=_workflow([_step("s0", "plan_research")])
    )
    decision = await wf_tools.edit_workflow_steps_check(
        {
            "store": store,
            "workflow_name": "weekly",
            "steps_json": _steps_json(_item("s0", "plan_messenger")),
        },
        MagicMock(),
    )
    assert decision.kind == "ask"
    assert "Step 1 (plan_messenger) may: send an email" in decision.reason


async def test_edit_steps_check_asks_even_when_nothing_is_planned() -> None:
    store = AsyncMock()
    store.get_by_name = AsyncMock(
        return_value=_workflow([_step("s0", "plan_research")])
    )
    decision = await wf_tools.edit_workflow_steps_check(
        {
            "store": store,
            "workflow_name": "weekly",
            "steps_json": _steps_json(_item("s0", "plan_research", "new task")),
        },
        MagicMock(),
    )
    assert decision.kind == "ask"
    assert "may:" not in decision.reason


async def _edit(store, steps_json: str, approval) -> dict:
    token = current_approval.set(approval)
    try:
        return await wf_tools.edit_workflow_steps(
            store=store, workflow_name="weekly", steps_json=steps_json
        )
    finally:
        current_approval.reset(token)


def _edit_store(existing: list[WorkflowStep]) -> AsyncMock:
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=_workflow(existing))
    return store


async def test_edit_clears_changed_steps_and_regrants_them_on_approval() -> None:
    existing = [
        _step(
            "s0",
            "plan_messenger",
            "send the digest",
            approved_writes=["plan_send_email"],
        ),
        _step(
            "s1",
            "plan_messenger",
            "archive old",
            approved_writes=["plan_archive_email"],
        ),
    ]
    store = _edit_store(existing)
    changed = _steps_json(
        _item("s0", "plan_messenger", "send a different digest"),
        _item("s1", "plan_messenger", "archive old"),
    )
    await _edit(store, changed, {"request_id": "r", "outcome": "approved"})
    saved = store.update_steps.await_args.args[1]
    assert saved[0].approved_writes == ["plan_send_email", "plan_archive_email"]
    assert saved[1].approved_writes == ["plan_archive_email"]


async def test_edit_without_approval_clears_changed_steps_only() -> None:
    existing = [
        _step(
            "s0",
            "plan_messenger",
            "send the digest",
            approved_writes=["plan_send_email"],
        ),
        _step(
            "s1",
            "plan_messenger",
            "archive old",
            approved_writes=["plan_archive_email"],
        ),
    ]
    store = _edit_store(existing)
    changed = _steps_json(
        _item("s0", "plan_messenger", "send a different digest"),
        _item("s1", "plan_messenger", "archive old"),
    )
    await _edit(store, changed, None)
    saved = store.update_steps.await_args.args[1]
    assert saved[0].approved_writes == []
    assert saved[1].approved_writes == ["plan_archive_email"]


async def test_edit_never_trusts_approved_writes_in_the_json() -> None:
    store = _edit_store([_step("s0", "plan_research", "a")])
    payload = _steps_json(
        {**_item("s0", "plan_messenger", "b"), "approved_writes": ["delete_event"]}
    )
    await _edit(store, payload, None)
    assert store.update_steps.await_args.args[1][0].approved_writes == []


def _goal_planner(milestones: list[Milestone]):
    from ze_automation.goals.planner import GoalPlanner

    planner = GoalPlanner(client=MagicMock(), memory_store=None, embedder=None)
    planner.plan = AsyncMock(return_value=(milestones, []))  # type: ignore[method-assign]
    return planner


def _goal_store() -> AsyncMock:
    store = AsyncMock()
    store.list_active = AsyncMock(return_value=[])
    store.list_completed_milestone_summaries = AsyncMock(return_value=[])
    store.create_goal = AsyncMock(
        side_effect=lambda g: Goal(
            title=g.title,
            objective=g.objective,
            success_condition=g.success_condition,
            id=uuid4(),
        )
    )
    return store


_GOAL_ARGS = {
    "goal_title": "Outreach",
    "objective": "contact 20 leads",
    "success_condition": "20 replies",
}


async def test_create_goal_check_asks_for_milestones_that_plan_writes() -> None:
    milestones = [
        Milestone(goal_id=uuid4(), title="find", description="", sequence=1),
        Milestone(
            goal_id=uuid4(),
            title="mail",
            description="",
            sequence=2,
            agent_hint="plan_messenger",
        ),
    ]
    decision = await goal_tools.create_goal_check(
        {"store": _goal_store(), "planner": _goal_planner(milestones), **_GOAL_ARGS},
        MagicMock(),
    )
    assert decision.kind == "ask"
    assert "Milestone 2 (plan_messenger) may: send an email" in decision.reason


async def test_approving_create_goal_stores_approved_writes_on_milestones() -> None:
    milestones = [
        Milestone(
            goal_id=uuid4(),
            title="mail",
            description="",
            sequence=1,
            agent_hint="plan_messenger",
        )
    ]
    planner = _goal_planner(milestones)
    store = _goal_store()
    await goal_tools.create_goal_check(
        {"store": store, "planner": planner, **_GOAL_ARGS}, MagicMock()
    )
    token = current_approval.set({"request_id": "r", "outcome": "approved"})
    try:
        await goal_tools.create_goal(
            store=store, planner=planner, notifier=AsyncMock(), **_GOAL_ARGS
        )
    finally:
        current_approval.reset(token)
    created = store.create_milestone.await_args.args[0]
    assert created.approved_writes == ["plan_send_email", "plan_archive_email"]
