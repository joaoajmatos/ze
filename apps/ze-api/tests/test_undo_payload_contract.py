"""Undo payloads match their undo tools, and each round trip restores the store (Phase 180 T023)."""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from tests.test_tool_reversibility import _load_all_tool_modules
from ze_agents.base_agent import _merge_deps
from ze_agents.park import ApprovedCall
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import (
    ToolAccess,
    get_tool,
    registered_tools,
    validate_tool_declarations,
)
from ze_agents.types import AgentContext

# Phase 180 plan D1: the payload each REVERSIBLE tool returns and its undo tool.
PAYLOAD_KEYS = {
    "set_reminder": ("cancel_reminder", {"reminder_id"}),
    "create_goal": ("abandon_goal", {"goal_id"}),
    # Phase 181 made pause/resume a REVERSIBLE pair; each undoes the other.
    "pause_goal": ("resume_goal", {"goal_id"}),
    "resume_goal": ("pause_goal", {"goal_id"}),
    "create_workflow": ("delete_workflow", {"workflow_name"}),
    "enable_workflow": ("disable_workflow", {"workflow_name"}),
    "disable_workflow": ("enable_workflow", {"workflow_name"}),
    "remember_fact": ("forget_fact", {"fact_id", "restore_fact_ids"}),
    "track_loop": ("drop_loop", {"loop_id"}),
    "confirm_loop": ("drop_loop", {"loop_id"}),
    "reprioritize_item": (
        "restore_priority_override",
        {"override_id", "prior_override_id"},
    ),
}


def test_every_reversible_tool_is_in_the_payload_table() -> None:
    _load_all_tool_modules()
    reversible = {
        name
        for name, spec in registered_tools().items()
        if spec.access is ToolAccess.WRITE
        and spec.reversibility is ToolReversibility.REVERSIBLE
    }
    assert reversible == set(PAYLOAD_KEYS)


def test_payload_keys_are_parameters_of_the_undo_tool() -> None:
    _load_all_tool_modules()
    for name, (undo_tool, keys) in PAYLOAD_KEYS.items():
        spec = get_tool(name)
        assert spec.undo_tool == undo_tool, name
        params = set(inspect.signature(get_tool(undo_tool).func).parameters)
        assert keys <= params, f"{name}: {keys - params} not accepted by {undo_tool}"


def test_declarations_validate_with_the_restore_tool_registered() -> None:
    _load_all_tool_modules()
    assert "restore_priority_override" in registered_tools()
    validate_tool_declarations()


# ── round trips with in-memory fakes (SC-001) ────────────────────────────────


def _ctx() -> AgentContext:
    return AgentContext(session_id="t1", prompt="x")


@pytest.fixture(autouse=True)
def _tools():
    _load_all_tool_modules()


async def _call(agent, name: str, **llm_args):
    """Call a tool the way the agent loop does: model args plus the agent's deps."""
    merged = _merge_deps(name, llm_args, agent.tool_deps())
    # The forward write runs as the user approved it (Phase 181 park and resume).
    return await agent.call_tool(
        name, _ctx(), _lm_args=llm_args, _approval=ApprovedCall("test"), **merged
    )


async def _undo(agent, call):
    assert call.success is True, call.error
    assert call.undo is not None, "tool returned no undo payload"
    tool_name = get_tool(call.tool_name).undo_tool
    undone = await agent.run_undo(tool_name, call.undo, session_id="t1")
    assert undone.success is True, undone.error
    return undone


class _ReminderStore:
    def __init__(self) -> None:
        self.rows: dict[UUID, SimpleNamespace] = {}

    async def create(self, label, fire_at):
        rid = uuid4()
        self.rows[rid] = SimpleNamespace(id=rid, label=label, fire_at=fire_at)
        return rid

    async def get(self, rid):
        return self.rows.get(rid)

    async def delete(self, rid):
        self.rows.pop(rid, None)


async def test_reminder_round_trip_cancels_it_and_its_job() -> None:
    from ze_calendar.agents.reminders.agent import RemindersAgent

    store, scheduler = _ReminderStore(), MagicMock()
    agent = RemindersAgent(MagicMock(), store, scheduler, MagicMock(), MagicMock())
    before = dict(store.rows)
    fire_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    call = await _call(agent, "set_reminder", label="call Ana", fire_at=fire_at)
    assert len(store.rows) == 1
    await _undo(agent, call)
    assert store.rows == before
    [job] = scheduler.remove_job_if_exists.call_args.args
    assert job == f"user_reminder:{call.undo['reminder_id']}"


class _GoalStore:
    def __init__(self) -> None:
        self.goals: dict[UUID, SimpleNamespace] = {}

    async def list_active(self):
        return []

    async def list_completed_milestone_summaries(self, **kw):
        return []

    async def create_goal(self, goal):
        goal.id = uuid4()
        self.goals[goal.id] = goal
        return goal

    async def create_milestone(self, m):
        return m

    async def create_gate(self, g):
        return g

    async def get_goal(self, gid):
        return self.goals.get(gid)

    async def update_status(self, gid, status):
        self.goals[gid].status = status


async def test_goal_round_trip_abandons_it_and_it_cannot_be_approved() -> None:
    from ze_automation.agents.goals.agent import GoalAgent
    from ze_automation.goals import proposal as goal_proposal
    from ze_automation.goals.executor import GoalExecutor
    from ze_automation.goals.types import GoalStatus

    store = _GoalStore()
    planner = MagicMock()
    planner.plan = AsyncMock(return_value=([], []))
    notifier = MagicMock()
    notifier.notify = AsyncMock()
    executor = object.__new__(GoalExecutor)
    executor._store = store
    executor._held_store = None
    agent = GoalAgent(MagicMock(), store, planner, executor, notifier)
    with patch.object(goal_proposal, "_check_convergence", AsyncMock()):
        call = await _call(
            agent,
            "create_goal",
            goal_title="Run a marathon",
            objective="o",
            success_condition="s",
        )
    [goal] = store.goals.values()
    assert goal.status is GoalStatus.PLANNING
    await _undo(agent, call)
    assert goal.status is GoalStatus.ABANDONED
    # the Start button from the plan notification cannot revive it (review J1)
    assert await executor.approve_plan(goal.id) is False
    assert goal.status is GoalStatus.ABANDONED


class _WorkflowStore:
    def __init__(self) -> None:
        self.rows: dict[UUID, SimpleNamespace] = {}

    async def create(self, workflow, actor=None):
        workflow.id = uuid4()
        self.rows[workflow.id] = workflow
        return workflow.id

    async def get_by_name(self, name):
        return next((w for w in self.rows.values() if w.name == name), None)

    async def delete(self, wid):
        self.rows.pop(wid, None)

    async def set_enabled(self, wid, enabled):
        self.rows[wid].enabled = enabled


def _workflow_agent(store, scheduler):
    from ze_automation.agents.workflow.agent import WorkflowManagerAgent

    planner = MagicMock()
    planner.plan = AsyncMock(return_value=[])
    planner.extract_schedule = AsyncMock(return_value=None)
    return WorkflowManagerAgent(MagicMock(), store, planner, scheduler)


async def test_workflow_create_round_trip_deletes_it_and_unschedules() -> None:
    store = _WorkflowStore()
    scheduler = MagicMock()
    scheduler.add_workflow = AsyncMock()
    scheduler.remove_workflow = AsyncMock()
    agent = _workflow_agent(store, scheduler)
    with patch(
        "ze_automation.agents.workflow.tools.validate_step_targets", lambda s: None
    ):
        call = await _call(
            agent,
            "create_workflow",
            workflow_name="Daily digest",
            description="d",
        )
    [wf] = store.rows.values()
    await _undo(agent, call)
    assert store.rows == {}
    scheduler.remove_workflow.assert_awaited_once_with(wf.id)


@pytest.mark.parametrize("start_enabled", [False, True])
async def test_workflow_enable_disable_round_trip_restores_flag_and_scheduler(
    start_enabled: bool,
) -> None:
    store = _WorkflowStore()
    wf = SimpleNamespace(id=uuid4(), name="Digest", enabled=start_enabled)
    store.rows[wf.id] = wf
    scheduler = MagicMock()
    scheduler.add_workflow = AsyncMock()
    scheduler.remove_workflow = AsyncMock()
    agent = _workflow_agent(store, scheduler)
    tool_name = "disable_workflow" if start_enabled else "enable_workflow"
    call = await _call(agent, tool_name, workflow_name="Digest")
    assert wf.enabled is (not start_enabled)
    scheduler.add_workflow.reset_mock()
    scheduler.remove_workflow.reset_mock()
    await _undo(agent, call)
    assert wf.enabled is start_enabled
    # the undo also moves the scheduler back (review J3)
    if start_enabled:
        scheduler.add_workflow.assert_awaited_once()
        scheduler.remove_workflow.assert_not_awaited()
    else:
        scheduler.remove_workflow.assert_awaited_once_with(wf.id)
        scheduler.add_workflow.assert_not_awaited()


@pytest.mark.parametrize("start_enabled", [False, True])
async def test_workflow_noop_toggle_returns_no_payload(start_enabled: bool) -> None:
    store = _WorkflowStore()
    wf = SimpleNamespace(id=uuid4(), name="Digest", enabled=start_enabled)
    store.rows[wf.id] = wf
    scheduler = MagicMock()
    scheduler.add_workflow = AsyncMock()
    scheduler.remove_workflow = AsyncMock()
    agent = _workflow_agent(store, scheduler)
    tool_name = "enable_workflow" if start_enabled else "disable_workflow"
    call = await _call(agent, tool_name, workflow_name="Digest")
    assert call.success is True
    assert call.undo is None


class _LoopLifecycle:
    def __init__(self) -> None:
        self.loops: dict[UUID, SimpleNamespace] = {}

    async def drop(self, lid):
        from ze_worldstate.types import LoopState

        self.loops[lid].state = LoopState.DROPPED
        return self.loops[lid]


async def test_loop_round_trip_drops_a_created_loop_only() -> None:
    from ze_worldstate.agents.agent import LoopsAgent
    from ze_worldstate.types import LoopState, TrackOutcome

    lifecycle = _LoopLifecycle()
    loop = SimpleNamespace(id=uuid4(), title="tax return", state=LoopState.ACTIVE)
    lifecycle.loops[loop.id] = loop
    tracker = MagicMock()
    outcomes = iter([TrackOutcome.CREATED, TrackOutcome.REINFORCED])
    tracker.track = AsyncMock(
        side_effect=lambda t, w, s=None: SimpleNamespace(
            ok=True, outcome=next(outcomes), loop=loop, error=None
        )
    )
    agent = LoopsAgent(MagicMock(), MagicMock(), tracker, lifecycle)
    created = await _call(agent, "track_loop", title="tax return")
    await _undo(agent, created)
    assert loop.state is LoopState.DROPPED

    reinforced = await _call(agent, "track_loop", title="tax return")
    assert reinforced.success is True
    assert reinforced.undo is None
