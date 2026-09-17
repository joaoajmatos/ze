from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from ze_agents.interrupt import workspace_run_origin
from ze_automation.goals.executor import GoalExecutor
from ze_automation.goals.types import Goal, GoalStatus, Milestone, MilestoneStatus
from ze_automation.workspace_unattended import consult_unattended, unattended_workspace


class FakeGate:
    def __init__(self, table: dict[str, str]):
        self.table = table
        self.calls: list[tuple[str, str]] = []

    def decide(self, *, action, origin):
        action_v = getattr(action, "value", action)
        origin_v = getattr(origin, "value", origin)
        self.calls.append((str(action_v), str(origin_v)))
        return self.table[str(action_v)]


def test_unattended_consults_allow():
    gate = FakeGate({"run": "allow", "run_script": "allow", "write": "allow"})
    assert consult_unattended(gate, action="run") == "allow"
    assert consult_unattended(gate, action="write") == "allow"
    assert all(origin == "unattended" for _, origin in gate.calls)


async def test_unattended_context_sets_origin_and_consults_gate():
    gate = FakeGate({"run": "allow", "run_script": "allow", "write": "allow"})
    async with unattended_workspace(gate) as decisions:
        assert workspace_run_origin.get() == "unattended"
        assert decisions["run"] == "allow"
        assert {action for action, _ in gate.calls} >= {"run", "run_script", "write"}
        assert all(origin == "unattended" for _, origin in gate.calls)
    assert workspace_run_origin.get() == "conversation"


async def test_goal_executor_consults_gate_with_unattended_origin():
    gate = FakeGate({"run": "allow", "run_script": "allow", "write": "allow"})
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(response="ok", tool_calls=[]))
    store = AsyncMock()
    executor = GoalExecutor(
        goal_store=store,
        goal_planner=MagicMock(),
        push=lambda _: None,
        agent_getter=lambda _name: agent,
        workspace_gate=gate,
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
    assert all(origin == "unattended" for _, origin in gate.calls)
    assert workspace_run_origin.get() == "conversation"
