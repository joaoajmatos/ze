from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from ze_agents.interrupt import workspace_run_origin
from ze_automation.goals.executor import GoalExecutor
from ze_automation.goals.types import Goal, GoalStatus, Milestone, MilestoneStatus
from ze_automation.workspace_unattended import consult_unattended, unattended_workspace


class FakeGate:
    def __init__(self, table: dict[tuple[str, str], str]):
        self.table = table
        self.calls: list[tuple[str, str, str]] = []

    def decide(self, *, mode, action, origin):
        mode_v = getattr(mode, "value", mode)
        action_v = getattr(action, "value", action)
        origin_v = getattr(origin, "value", origin)
        self.calls.append((str(mode_v), str(action_v), str(origin_v)))
        return self.table[(str(mode_v), str(action_v))]


def test_ask_plan_off_skip_unattended_run_and_script():
    for mode in ("ask", "plan", "off"):
        gate = FakeGate(
            {
                (mode, "run"): "deny",
                (mode, "run_script"): "deny",
                (mode, "write"): "deny",
            }
        )
        assert consult_unattended(gate, mode=mode, action="run") == "deny"
        assert consult_unattended(gate, mode=mode, action="run_script") == "deny"
        assert all(origin == "unattended" for _, _, origin in gate.calls)


def test_auto_edit_skips_unattended_commands_but_may_write():
    gate = FakeGate(
        {
            ("auto_edit", "run"): "deny",
            ("auto_edit", "run_script"): "deny",
            ("auto_edit", "write"): "allow",
        }
    )
    assert consult_unattended(gate, mode="auto_edit", action="run") == "deny"
    assert consult_unattended(gate, mode="auto_edit", action="run_script") == "deny"
    assert consult_unattended(gate, mode="auto_edit", action="write") == "allow"


def test_auto_may_run_unattended():
    gate = FakeGate(
        {
            ("auto", "run"): "allow",
            ("auto", "run_script"): "allow",
            ("auto", "write"): "allow",
        }
    )
    assert consult_unattended(gate, mode="auto", action="run") == "allow"
    assert consult_unattended(gate, mode="auto", action="run_script") == "allow"


async def test_unattended_context_sets_origin_and_consults_gate():
    gate = FakeGate(
        {
            ("auto", "run"): "allow",
            ("auto", "run_script"): "allow",
            ("auto", "write"): "allow",
        }
    )
    get_mode = AsyncMock(return_value="auto")
    async with unattended_workspace(gate, get_mode) as decisions:
        assert workspace_run_origin.get() == "unattended"
        assert decisions["run"] == "allow"
        assert {action for action, *_ in [(c[1],) for c in gate.calls]} >= {
            "run",
            "run_script",
            "write",
        }
        assert all(c[2] == "unattended" for c in gate.calls)
    assert workspace_run_origin.get() == "conversation"


async def test_goal_executor_consults_gate_with_unattended_origin():
    gate = FakeGate(
        {
            ("ask", "run"): "deny",
            ("ask", "run_script"): "deny",
            ("ask", "write"): "deny",
        }
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(response="ok", tool_calls=[]))
    store = AsyncMock()
    executor = GoalExecutor(
        goal_store=store,
        goal_planner=MagicMock(),
        push=lambda _: None,
        agent_getter=lambda _name: agent,
        workspace_gate=gate,
        get_workspace_mode=AsyncMock(return_value="ask"),
    )
    goal_id = uuid4()
    goal = Goal(
        id=goal_id,
        title="T",
        objective="O",
        success_condition="S",
        status=GoalStatus.ACTIVE,
    )
    milestone = Milestone(
        id=uuid4(),
        goal_id=goal_id,
        title="step",
        description="do it",
        sequence=1,
        status=MilestoneStatus.IN_PROGRESS,
    )
    await executor._execute_milestone(milestone, goal, [milestone])
    assert agent.run.await_count == 1
    assert gate.calls
    assert all(origin == "unattended" for _, _, origin in gate.calls)
    assert workspace_run_origin.get() == "conversation"
