"""Unattended workflow runs: pre-approved writes run, anything else holds (Phase 181, US5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

import ze_agents.registry as registry_mod
import ze_agents.tool as tool_mod
from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent, register_instance
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import AskDecision, ToolAccess, tool
from ze_agents.types import AgentContext, AgentResult
from ze_api.wiring.workflow_graph import build_workflow_graph
from ze_automation.holds.resumer import HeldWriteResumer
from ze_automation.holds.store import HeldWriteStore
from ze_automation.holds.types import HeldWrite, HeldWriteStatus
from ze_automation.push_kinds import WRITE_APPROVAL_HELD
from ze_automation.workflow.runner import WorkflowRunner
from ze_automation.workflow.scheduler import WorkflowScheduler
from ze_automation.workflow.types import Workflow, WorkflowStep
from ze_core.conversation import make_graph_input
from ze_core.orchestration.state import build_state_type
from ze_core.routing.types import RoutingEnvelope, SubTask

calls: list[str] = []
probes: list = []


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
    monkeypatch.setattr(tool_mod, "_tools", dict(tool_mod._tools))
    monkeypatch.setattr(registry_mod, "_instances", dict(registry_mod._instances))
    calls.clear()
    probes.clear()

    async def hold_send_email(to: str = "") -> str:
        calls.append("send_email")
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
        constraint_gate=True,
    )(hold_send_email)

    async def hold_delete_event(event_id: str = "") -> str:
        calls.append("delete_event")
        for probe in probes:
            probe()
        return "deleted"

    tool(
        access=ToolAccess.WRITE,
        description="delete",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
    )(hold_delete_event)


class Harness:
    """A compiled workflow graph with real execution nodes and a scripted agent."""

    def __init__(self, scripts: list[tuple]) -> None:
        queue = list(scripts)
        client = MagicMock()

        async def _complete(**kw):
            return queue.pop(0)

        client.complete_with_tools = AsyncMock(side_effect=_complete)
        client.complete = AsyncMock(return_value="summary")
        self.client = client

        async def _run(this, ctx: AgentContext) -> AgentResult:
            text, tcs = await this.agentic_loop(
                ctx,
                client,
                list(ctx.messages),
                system="s",
                tool_names=["hold_send_email", "hold_delete_event"],
            )
            return AgentResult(agent=this.name, response=text, tool_calls=tcs)

        cls = type(
            "_HoldAgent",
            (BaseAgent,),
            {
                "name": "holdagent",
                "description": "d",
                "tools": ["hold_send_email", "hold_delete_event"],
                "run": _run,
            },
        )
        agent(cls)
        register_instance("holdagent", cls())

        self.workflow_store = AsyncMock()
        self.exec_status: dict = {}

        async def _set_status(execution_id, status, expected=None):
            if expected is not None and self.exec_status.get(execution_id) != expected:
                return False
            self.exec_status[execution_id] = status
            return True

        async def _finish(execution_id, status, error=None, summary=None):
            self.exec_status[execution_id] = status

        async def _get_execution(workflow_id, execution_id):
            return SimpleNamespace(
                status=self.exec_status.get(execution_id, "running"), error=None
            )

        self.workflow_store.set_execution_status = AsyncMock(side_effect=_set_status)
        self.workflow_store.finish_execution = AsyncMock(side_effect=_finish)
        self.workflow_store.get_execution = AsyncMock(side_effect=_get_execution)
        self.held = MemoryHeldStore()
        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock(return_value="sent")
        self.saver = MemorySaver()
        self.graph = self._graph()
        self.workflow = Workflow(
            id=uuid4(),
            name="Weekly summary",
            description="d",
            steps=[],
            schedule=None,
            enabled=True,
            last_run_at=None,
            next_run_at=None,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        self.workflow_store.get = AsyncMock(return_value=self.workflow)
        self.scheduler = WorkflowScheduler(self.workflow_store, enabled=False)
        self.runner = WorkflowRunner(
            scheduler=self.scheduler,
            graph=self.graph,
            configurable={
                "openrouter_client": client,
                "workflow_store": self.workflow_store,
            },
            workflow_store=self.workflow_store,
            held_store=self.held,
            notifier=self.notifier,
        )
        self.resumer = HeldWriteResumer(self.held, resume_workflow=self.runner.resume)

    def _graph(self):
        async def noop(state, config=None):
            return {}

        async def embed_route(state):
            envelope = RoutingEnvelope(
                primary_agent="holdagent",
                confidence=1.0,
                score_gap=1.0,
                routing_method="forced",
                is_compound=False,
                subtasks=[SubTask(agent="holdagent", prompt=state["prompt"])],
                requires_synthesis=False,
            )
            return {"envelope": envelope}

        async def fetch_context(state):
            return {
                "agent_context": AgentContext(
                    session_id=state["session_id"],
                    prompt=state["prompt"],
                    messages=[{"role": "user", "content": state["prompt"]}],
                )
            }

        overrides = {
            "preprocess": noop,
            "embed_route": embed_route,
            "decompose": noop,
            "fetch_context": fetch_context,
            "match_skills": noop,
            "correlate": noop,
            "surface_loops": noop,
            "write_memory": noop,
        }
        return build_workflow_graph(
            self.saver, plugins=[_StatePlugin()], node_overrides=overrides
        )

    def initial_state(self, steps: list[WorkflowStep], execution_id) -> dict:
        from ze_agents.interface.types import RawInput

        self.workflow.steps = steps
        return {
            **make_graph_input(
                RawInput(text="[workflow]"),
                f"workflow:{self.workflow.id}",
                build_state_type([_StatePlugin()]),
            ),
            "workflow_id": self.workflow.id,
            "workflow_execution_id": execution_id,
            "workflow_steps": steps,
            "current_step_id": steps[0].id,
            "workflow_step_results": [],
        }

    async def run(self, steps: list[WorkflowStep]):
        execution_id = uuid4()
        await self.runner.run(
            self.workflow, execution_id, self.initial_state(steps, execution_id)
        )
        return execution_id


class _StatePlugin:
    """Contributes the workflow state keys and the workflow-only graph nodes."""

    def state_extensions(self):
        from ze_personal.graph.workflow import WorkflowAgentState

        return WorkflowAgentState

    def graph_nodes(self):
        return {}

    def graph_edges(self, builder):
        return None


def _steps() -> list[WorkflowStep]:
    return [
        WorkflowStep(task="gather", id="s0"),
        WorkflowStep(
            task="send the digest",
            id="s1",
            approved_writes=["hold_send_email"],
        ),
    ]


def _digest_script():
    return [
        ("gathered", None),
        (None, [_tc("c1", "hold_send_email", to="me@x.io")]),
        ("Sent the digest.", None),
    ]


async def test_a_pre_approved_write_runs_unasked_and_does_not_hold() -> None:
    h = Harness(_digest_script())
    await h.run(_steps())
    assert calls == ["send_email"]
    assert h.held.rows == {}
    h.notifier.notify.assert_not_awaited()


async def test_running_a_pre_approved_workflow_in_a_loop_never_asks() -> None:
    h = Harness(_digest_script() * 4)
    for _ in range(4):
        await h.run(_steps())
        assert h.held.rows == {}
        h.notifier.notify.assert_not_awaited()
    assert calls == ["send_email"] * 4


def _delete_script():
    return [
        (None, [_tc("c1", "hold_delete_event", event_id="e1")]),
        ("Deleted it.", None),
    ]


def _delete_steps() -> list[WorkflowStep]:
    return [WorkflowStep(task="tidy my calendar", id="s0")]


async def test_an_unplanned_write_holds_the_run_and_pushes_once() -> None:
    h = Harness(_delete_script())
    execution_id = await h.run(_delete_steps())

    assert calls == []
    assert len(h.held.rows) == 1
    hold = next(iter(h.held.rows.values()))
    assert hold.source == "workflow"
    assert hold.owner_ref == str(execution_id)
    assert hold.status is HeldWriteStatus.OPEN
    assert hold.payload["source_name"] == "Weekly summary"
    assert hold.items[0]["tool"] == "hold_delete_event"
    assert hold.expires_at is not None
    delta = hold.expires_at - datetime.now(tz=timezone.utc)
    assert timedelta(hours=23, minutes=50) < delta <= timedelta(hours=24)
    h.workflow_store.set_execution_status.assert_awaited_once_with(execution_id, "held")
    assert h.notifier.notify.await_count == 1
    kind, title, _body = h.notifier.notify.await_args.args
    assert kind is WRITE_APPROVAL_HELD
    assert title == "Workflow 'Weekly summary' needs your OK"
    assert h.notifier.notify.await_args.kwargs["target_id"] == hold.request_id


async def test_approving_a_held_write_runs_the_call_once_and_the_run_continues() -> (
    None
):
    h = Harness(_delete_script())
    execution_id = await h.run(_delete_steps())
    request_id = next(iter(h.held.rows))

    await h.resumer.resume(request_id, "approve")

    assert calls == ["delete_event"]
    assert h.held.rows[request_id].status is HeldWriteStatus.APPROVED
    h.workflow_store.set_execution_status.assert_any_await(
        execution_id, "running", expected="held"
    )
    h.workflow_store.finish_execution.assert_awaited()
    assert h.workflow_store.finish_execution.await_args.args[1] == "completed"


async def test_denying_continues_with_the_declined_result_and_never_runs_the_call() -> (
    None
):
    h = Harness(_delete_script())
    await h.run(_delete_steps())
    request_id = next(iter(h.held.rows))

    await h.resumer.resume(request_id, "deny")

    assert calls == []
    assert h.held.rows[request_id].status is HeldWriteStatus.DENIED
    assert h.workflow_store.finish_execution.await_args.args[1] == "completed"


async def test_a_held_write_can_only_be_answered_once() -> None:
    from ze_automation.holds.resumer import HeldWriteNotOpenError

    h = Harness(_delete_script())
    await h.run(_delete_steps())
    request_id = next(iter(h.held.rows))
    await h.resumer.resume(request_id, "approve")
    with pytest.raises(HeldWriteNotOpenError):
        await h.resumer.resume(request_id, "approve")
    assert calls == ["delete_event"]


class _ConstraintHook:
    def __init__(self, decision: AskDecision) -> None:
        self._decision = decision

    async def check_call(self, event) -> AskDecision:
        return self._decision

    async def on_tool_start(self, event):
        return None

    async def on_tool_end(self, event):
        return None


async def test_a_reviewed_constraint_holds_even_a_pre_approved_write(
    monkeypatch,
) -> None:
    import ze_agents.hooks as hooks_mod

    monkeypatch.setattr(
        hooks_mod,
        "_hooks",
        [_ConstraintHook(AskDecision.ask("You said never email X"))],
    )
    h = Harness(_digest_script())
    await h.run(_steps())

    assert calls == []
    hold = next(iter(h.held.rows.values()))
    assert hold.items[0]["tool"] == "hold_send_email"
    assert hold.items[0]["conflict"] == "You said never email X"


async def test_a_hard_veto_refuses_a_pre_approved_write_without_holding(
    monkeypatch,
) -> None:
    import ze_agents.hooks as hooks_mod

    monkeypatch.setattr(
        hooks_mod,
        "_hooks",
        [_ConstraintHook(AskDecision.refuse("Blocked by your rule."))],
    )
    h = Harness(_digest_script() + [("done", None)])
    await h.run(_steps())

    assert calls == []
    assert h.held.rows == {}


async def test_a_refused_veto_fails_the_step_and_the_run(monkeypatch) -> None:
    import ze_agents.hooks as hooks_mod

    monkeypatch.setattr(
        hooks_mod,
        "_hooks",
        [_ConstraintHook(AskDecision.refuse("Blocked by your rule."))],
    )
    h = Harness(_digest_script() + [("done", None)])
    execution_id = await h.run(_steps())

    assert h.exec_status[execution_id] == "failed"


async def test_a_denied_step_leaves_no_write_state_for_the_next_step() -> None:
    steps = [
        WorkflowStep(task="tidy my calendar", id="s0"),
        WorkflowStep(task="say hello", id="s1"),
    ]
    h = Harness(_delete_script() + [("Hello.", None)])
    execution_id = await h.run(steps)
    request_id = next(iter(h.held.rows))

    await h.resumer.resume(request_id, "deny")

    state = await h.graph.aget_state({"configurable": {"thread_id": str(execution_id)}})
    results = state.values["workflow_step_results"]
    assert [r.step_id for r in results] == ["s0", "s1"]
    assert "didn't" in results[0].output
    assert "didn't" not in results[1].output
    assert state.values["write_rounds"] == 0
    assert state.values["write_outcomes"] == []
    assert h.exec_status[execution_id] == "completed"


async def test_a_resumed_run_is_tracked_by_the_scheduler() -> None:
    h = Harness(_delete_script())
    execution_id = await h.run(_delete_steps())
    request_id = next(iter(h.held.rows))
    seen: list[bool] = []
    probes.append(lambda: seen.append(execution_id in h.scheduler._running_executions))
    probes.append(
        lambda: seen.append(
            h.scheduler._cancellation.is_cancelled(execution_id) is False
        )
    )

    await h.resumer.resume(request_id, "approve")

    assert seen == [True, True]
    assert execution_id not in h.scheduler._running_executions
    h.workflow_store.update_run_timestamps.assert_awaited_once()


async def test_cancelling_a_held_run_denies_its_hold_and_it_cannot_resume() -> None:
    from ze_automation.holds.resumer import HeldWriteNotOpenError

    h = Harness(_delete_script())
    execution_id = await h.run(_delete_steps())
    request_id = next(iter(h.held.rows))
    h.scheduler.configure_held_canceller(h.runner.cancel_held)

    result = await h.scheduler.cancel_execution(h.workflow.id, execution_id)

    assert result == "cancelled"
    assert h.exec_status[execution_id] == "cancelled"
    assert h.held.rows[request_id].status is HeldWriteStatus.DENIED
    with pytest.raises(HeldWriteNotOpenError):
        await h.resumer.resume(request_id, "approve")
    assert calls == []


async def test_cancelling_loses_to_an_answer_that_already_claimed_the_hold() -> None:
    h = Harness(_delete_script())
    execution_id = await h.run(_delete_steps())
    request_id = next(iter(h.held.rows))
    await h.held.decide(request_id, HeldWriteStatus.APPROVED)

    await h.runner.cancel_held(execution_id)

    assert h.exec_status[execution_id] == "held"
