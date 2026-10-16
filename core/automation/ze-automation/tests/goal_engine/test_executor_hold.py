"""A goal milestone that reaches an unplanned asks-first write holds (Phase 181, US5)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import ze_agents.registry as registry_mod
import ze_agents.tool as tool_mod
from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent, get_agent, register_instance
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, tool
from ze_agents.types import AgentContext, AgentResult
from ze_automation.goals.executor import GoalExecutor
from ze_automation.goals.types import Goal, GoalStatus, Milestone, MilestoneStatus
from ze_automation.holds.resumer import HeldWriteResumer
from ze_automation.holds.store import HeldWriteStore
from ze_automation.holds.types import HeldWrite, HeldWriteStatus
from ze_automation.push_kinds import WRITE_APPROVAL_HELD

calls: list[str] = []


class MemoryHeldStore(HeldWriteStore):
    def __init__(self) -> None:
        self.rows: dict[str, HeldWrite] = {}

    async def create(self, hold: HeldWrite) -> None:
        self.rows[hold.request_id] = hold

    async def get(self, request_id: str) -> HeldWrite | None:
        return self.rows.get(request_id)

    async def list(self, status: HeldWriteStatus) -> list[HeldWrite]:
        return [h for h in self.rows.values() if h.status is status]

    async def decide(self, request_id: str, status: HeldWriteStatus) -> bool:
        row = self.rows.get(request_id)
        if row is None or row.status is not HeldWriteStatus.OPEN:
            return False
        row.status = status
        return True

    async def list_expired(self, now: datetime) -> list[HeldWrite]:
        return []


def _tc(id_: str, name: str, **args):
    return {"id": id_, "name": name, "arguments": args}


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    monkeypatch.setattr(registry_mod, "_registry", dict(registry_mod._registry))
    monkeypatch.setattr(registry_mod, "_instances", dict(registry_mod._instances))
    monkeypatch.setattr(tool_mod, "_tools", dict(tool_mod._tools))
    calls.clear()

    async def goal_send_email(to: str = "") -> str:
        calls.append("send_email")
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
    )(goal_send_email)


class Rig:
    def __init__(self, scripts: list[tuple], approved_writes: list[str] | None = None):
        queue = list(scripts)
        client = MagicMock()

        async def _complete(**kw):
            return queue.pop(0)

        client.complete_with_tools = AsyncMock(side_effect=_complete)

        async def _run(this, ctx: AgentContext) -> AgentResult:
            text, tcs = await this.agentic_loop(
                ctx,
                client,
                [{"role": "user", "content": ctx.prompt}],
                system="s",
                tool_names=["goal_send_email"],
            )
            return AgentResult(agent=this.name, response=text, tool_calls=tcs)

        cls = type(
            "_GoalAgent",
            (BaseAgent,),
            {
                "name": "goalagent",
                "description": "d",
                "tools": ["goal_send_email"],
                "run": _run,
            },
        )
        agent(cls)
        register_instance("goalagent", cls())

        self.goal = Goal(
            id=uuid4(),
            title="Outreach",
            objective="o",
            success_condition="s",
            status=GoalStatus.ACTIVE,
        )
        self.milestone = Milestone(
            id=uuid4(),
            goal_id=self.goal.id,
            title="Email the lead",
            description="send it",
            sequence=1,
            agent_hint="goalagent",
            approved_writes=approved_writes or [],
        )
        self.milestones = [self.milestone]
        store = AsyncMock()
        store.get_goal = AsyncMock(return_value=self.goal)
        store.list_milestones = AsyncMock(side_effect=lambda gid: list(self.milestones))
        store.get_pending_gate = AsyncMock(return_value=None)
        store.list_eligible_learnings = AsyncMock(return_value=[])
        store.list_completed_milestone_summaries = AsyncMock(return_value=[])

        async def _update(milestone_id, status, output=""):
            self.milestone.status = status
            self.milestone.output = output

        store.update_milestone = AsyncMock(side_effect=_update)
        self.store = store
        planner = AsyncMock()
        planner.extract_learning = AsyncMock(return_value="insight")
        self.notify = AsyncMock(return_value="sent")
        self.held = MemoryHeldStore()
        self.executor = GoalExecutor(
            goal_store=store,
            goal_planner=planner,
            notify=self.notify,
            agent_getter=get_agent,
            held_store=self.held,
        )
        self.executor.advance = AsyncMock()  # type: ignore[method-assign]
        self.resumer = HeldWriteResumer(
            self.held, resume_goal=self.executor.resume_held
        )

    async def advance(self) -> None:
        await GoalExecutor._advance_unlocked(self.executor, self.goal.id)


def _send_script():
    return [
        (None, [_tc("c1", "goal_send_email", to="lead@x.io")]),
        ("Emailed the lead.", None),
    ]


async def test_a_milestone_that_parks_is_held_with_its_loop_and_one_push() -> None:
    rig = Rig(_send_script())
    await rig.advance()

    assert calls == []
    assert rig.milestone.status is MilestoneStatus.HELD
    assert len(rig.held.rows) == 1
    hold = next(iter(rig.held.rows.values()))
    assert hold.source == "goal"
    assert hold.owner_ref == str(rig.milestone.id)
    assert hold.items[0]["tool"] == "goal_send_email"
    assert hold.payload["source_name"] == "Outreach"
    assert hold.payload["loop"]["agent"] == "goalagent"
    assert hold.payload["loop"]["parked"][0]["tool"] == "goal_send_email"
    rig.store.save_traces.assert_not_awaited()
    assert rig.notify.await_count == 1
    assert rig.notify.await_args.args[0] is WRITE_APPROVAL_HELD
    assert rig.notify.await_args.args[1] == "Goal 'Outreach' needs your OK"


async def test_approving_runs_the_call_once_and_the_milestone_continues() -> None:
    rig = Rig(_send_script())
    await rig.advance()
    request_id = next(iter(rig.held.rows))

    await rig.resumer.resume(request_id, "approve")

    assert calls == ["send_email"]
    assert rig.milestone.status is MilestoneStatus.COMPLETED
    assert rig.milestone.output == "Emailed the lead."
    assert rig.held.rows[request_id].status is HeldWriteStatus.APPROVED
    rig.store.save_traces.assert_awaited()
    rig.executor.advance.assert_called_with(rig.goal.id)


async def test_denying_never_runs_the_call_and_the_milestone_continues() -> None:
    rig = Rig(_send_script())
    await rig.advance()
    request_id = next(iter(rig.held.rows))

    await rig.resumer.resume(request_id, "deny")

    assert calls == []
    assert rig.milestone.status is MilestoneStatus.COMPLETED
    assert rig.held.rows[request_id].status is HeldWriteStatus.DENIED


async def test_a_pre_approved_milestone_tool_runs_unasked() -> None:
    rig = Rig(_send_script(), approved_writes=["goal_send_email"])
    await rig.advance()

    assert calls == ["send_email"]
    assert rig.held.rows == {}
    assert all(c.args[0] is not WRITE_APPROVAL_HELD for c in rig.notify.await_args_list)
    assert rig.milestone.status is MilestoneStatus.COMPLETED


async def test_advance_waits_while_a_milestone_is_held() -> None:
    rig = Rig(_send_script())
    await rig.advance()
    second = Milestone(
        id=uuid4(),
        goal_id=rig.goal.id,
        title="Next",
        description="later",
        sequence=2,
    )
    rig.milestones.append(second)
    rig.store.update_milestone.reset_mock()

    await rig.advance()

    rig.store.update_milestone.assert_not_awaited()
    assert second.status is MilestoneStatus.PENDING


async def test_resume_waits_for_the_advance_lock_before_touching_the_milestone() -> (
    None
):
    import asyncio

    rig = Rig(_send_script())
    await rig.advance()
    request_id = next(iter(rig.held.rows))
    hold = await rig.resumer.decide(request_id, "approve")

    async with rig.executor._advance_locks[rig.goal.id]:
        task = asyncio.create_task(rig.executor.resume_held(hold, "approve", {}))
        for _ in range(5):
            await asyncio.sleep(0)
        assert rig.milestone.status is MilestoneStatus.HELD
        assert calls == []
    await task

    assert rig.milestone.status is MilestoneStatus.COMPLETED
    assert calls == ["send_email"]


@pytest.mark.parametrize("status", [GoalStatus.PAUSED, GoalStatus.ABANDONED])
async def test_a_held_write_is_not_run_after_its_goal_stopped(status) -> None:
    rig = Rig(_send_script())
    await rig.advance()
    request_id = next(iter(rig.held.rows))
    rig.goal.status = status

    await rig.resumer.resume(request_id, "approve")

    assert calls == []
    assert rig.milestone.status is MilestoneStatus.PENDING


async def test_closing_a_goals_holds_denies_them_and_frees_the_milestone() -> None:
    from ze_automation.holds.resumer import HeldWriteNotOpenError

    rig = Rig(_send_script())
    await rig.advance()
    request_id = next(iter(rig.held.rows))

    await rig.executor.close_holds(rig.goal.id)

    assert rig.held.rows[request_id].status is HeldWriteStatus.DENIED
    assert rig.milestone.status is MilestoneStatus.PENDING
    with pytest.raises(HeldWriteNotOpenError):
        await rig.resumer.resume(request_id, "approve")
    assert calls == []


async def test_abandoning_a_goal_closes_its_open_holds() -> None:
    import ze_automation.agents.goals.tools as goal_tools

    rig = Rig(_send_script())
    await rig.advance()
    request_id = next(iter(rig.held.rows))
    rig.store.update_status = AsyncMock()

    await goal_tools.abandon_goal(
        store=rig.store, executor=rig.executor, goal_id=str(rig.goal.id)
    )

    assert rig.held.rows[request_id].status is HeldWriteStatus.DENIED
