from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_agents.types import AgentContext, AgentResult, ProcedureInvocation, ToolCall
from ze_core.conversation.messages.types import ProcedureUsageTrace
from ze_core.orchestration.nodes.trace import record_trace
from ze_core.orchestration.procedure_activation import (
    complete_procedure_invocations,
    record_guided_actions,
)
from ze_memory.procedures.types import (
    CapabilityDecision,
    ProcedureActionOutcome,
    ProcedureOutcome,
)


async def test_blocked_gate_records_not_executed_action_link() -> None:
    activator = SimpleNamespace(
        record_action=AsyncMock(),
        complete=AsyncMock(),
    )
    invocation_id = uuid4()
    invocation = ProcedureInvocation(
        invocation_id=str(invocation_id),
        procedure_id=str(uuid4()),
        version_id=str(uuid4()),
    )
    result = AgentResult(
        agent="companion",
        response="blocked",
        tool_calls=[
            ToolCall(
                tool_name="search_email",
                args={},
                result=None,
                duration_ms=0,
                success=False,
                error="refused",
                gate="denied",
            )
        ],
    )
    await record_guided_actions(
        invocation, result, {"configurable": {"procedure_activator": activator}}
    )
    kwargs = activator.record_action.await_args.kwargs
    assert kwargs["capability_decision"] is CapabilityDecision.DENIED
    assert kwargs["outcome"] is ProcedureActionOutcome.NOT_EXECUTED


async def test_complete_is_forwarded_once() -> None:
    activator = SimpleNamespace(complete=AsyncMock())
    invocation_id = uuid4()
    result = AgentResult(
        agent="companion",
        response="done",
        tool_calls=[
            ToolCall(
                tool_name="search_email",
                args={},
                result="ok",
                duration_ms=1,
                success=True,
            )
        ],
    )
    state = {
        "agent_result": result,
        "procedure_invocations": [
            ProcedureInvocation(
                invocation_id=str(invocation_id), procedure_id="p", version_id="v"
            )
        ],
    }
    await complete_procedure_invocations(
        state, {"configurable": {"procedure_activator": activator}}
    )
    activator.complete.assert_awaited_once()
    assert activator.complete.await_args.kwargs["outcome"] is ProcedureOutcome.SUCCEEDED


async def test_record_trace_includes_procedure_usage() -> None:
    procedure_id = uuid4()
    version_id = uuid4()
    invocation_id = uuid4()
    state = {
        "envelope": SimpleNamespace(
            primary_agent="companion",
            routing_method="embedding",
            confidence=0.9,
            score_gap=0.1,
            is_compound=False,
            subtasks=[],
        ),
        "agent_result": AgentResult(agent="companion", response="ok"),
        "procedure_invocations": [
            ProcedureInvocation(
                invocation_id=str(invocation_id),
                procedure_id=str(procedure_id),
                version_id=str(version_id),
            )
        ],
    }
    result = await record_trace(state, {"configurable": {}})
    assert result["message_trace"].procedure == ProcedureUsageTrace(
        invocation_id=str(invocation_id),
        procedure_id=str(procedure_id),
        version_id=str(version_id),
    )


async def test_a_duplicate_call_is_allowed_but_not_executed_here() -> None:
    activator = SimpleNamespace(record_action=AsyncMock(), complete=AsyncMock())
    invocation = ProcedureInvocation(
        invocation_id=str(uuid4()),
        procedure_id=str(uuid4()),
        version_id=str(uuid4()),
    )
    result = AgentResult(
        agent="reminders",
        response="done",
        tool_calls=[
            ToolCall(
                tool_name="cancel_reminder",
                args={},
                result="approved once; not repeated",
                duration_ms=0,
                success=True,
                gate="duplicate",
            )
        ],
    )
    await record_guided_actions(
        invocation, result, {"configurable": {"procedure_activator": activator}}
    )
    kwargs = activator.record_action.await_args.kwargs
    assert kwargs["capability_decision"] is CapabilityDecision.ALLOWED
    assert kwargs["outcome"] is ProcedureActionOutcome.NOT_EXECUTED


# ── Invocations travel in state (phase 200) ───────────────────────────────────


def _ok(name: str) -> ToolCall:
    return ToolCall(tool_name=name, args={}, result="ok", duration_ms=1, success=True)


def _bad(name: str) -> ToolCall:
    return ToolCall(
        tool_name=name,
        args={},
        result=None,
        duration_ms=1,
        success=False,
        error="boom",
    )


def _invoking_agent(name: str, calls: list[ToolCall], *, invoke: bool = True):
    """A stub agent that invokes a procedure (as `invoke_procedure` does) and acts."""
    from ze_agents.registry import agent, register_instance

    ids: dict = {}

    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            if invoke and ctx.procedure_invocation is None:
                ctx.procedure_invocation = ProcedureInvocation(
                    invocation_id=str(uuid4()),
                    procedure_id=f"p-{name}",
                    version_id=f"v-{name}",
                )
            if ctx.procedure_invocation is not None:
                ids[name] = ctx.procedure_invocation.invocation_id
            return AgentResult(agent=name, response=name, tool_calls=list(calls))

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = name
    _A.enabled = True
    _A.timeout = 30
    agent(_A)
    register_instance(name, _A())
    return ids


def _turn_state(names: list[str], **extra) -> dict:
    from ze_core.routing.types import RoutingEnvelope, SubTask

    compound = len(names) > 1
    return {
        "envelope": RoutingEnvelope(
            primary_agent=names[0],
            confidence=0.9,
            score_gap=0.3,
            routing_method="embedding",
            is_compound=compound,
            subtasks=[SubTask(agent=n, prompt="p") for n in names],
            requires_synthesis=compound,
        ),
        "agent_context": AgentContext(session_id="s1", prompt="p"),
        "image_data": None,
        **extra,
    }


@pytest.fixture
def registry():
    from ze_agents.registry import clear_registry

    clear_registry()
    yield
    clear_registry()


async def test_a_single_subtasks_invocation_is_the_turns_first_and_the_trace_shows_it(
    registry,
) -> None:
    from ze_core.orchestration.nodes.execution import execute_tool

    ids = _invoking_agent("a", [_ok("search_email")])
    out = await execute_tool(_turn_state(["a"]), {"configurable": {}})

    [invocation] = out["procedure_invocations"]
    assert invocation.invocation_id == ids["a"]
    assert invocation.subtask == 0
    traced = await record_trace({**_turn_state(["a"]), **out}, {"configurable": {}})
    assert traced["message_trace"].procedure.invocation_id == ids["a"]


async def test_two_invoking_subtasks_each_complete_with_their_own_result(
    registry,
) -> None:
    from ze_core.orchestration.nodes.execution import execute_tool

    activator = SimpleNamespace(record_action=AsyncMock(), complete=AsyncMock())
    config = {"configurable": {"procedure_activator": activator}}
    ids_a = _invoking_agent("a", [_bad("search_email")])
    ids_b = _invoking_agent("b", [_ok("send_email")])
    state = _turn_state(["a", "b"])
    out = await execute_tool(state, config)
    ids = ids_a | ids_b

    assert [i.subtask for i in out["procedure_invocations"]] == [0, 1]
    recorded = {
        call.args[0]: call.kwargs["step_ref"]
        for call in activator.record_action.await_args_list
    }
    assert {str(k): v for k, v in recorded.items()} == {
        ids["a"]: "search_email",
        ids["b"]: "send_email",
    }

    await complete_procedure_invocations({**state, **out}, config)
    outcomes = {
        str(call.args[0]): call.kwargs["outcome"]
        for call in activator.complete.await_args_list
    }
    assert outcomes == {
        ids["a"]: ProcedureOutcome.FAILED,
        ids["b"]: ProcedureOutcome.SUCCEEDED,
    }
    traced = await record_trace({**state, **out}, {"configurable": {}})
    assert traced["message_trace"].procedure.invocation_id == ids["a"]


async def test_an_invocation_survives_a_pause_and_is_completed_after_the_resume(
    registry,
) -> None:
    from langgraph.types import Command

    from ze_agents.tool import clear_tool_registry
    from tests.orchestration import write_confirmation_harness as h
    from ze_core.routing.types import SubTask

    clear_tool_registry()
    h.calls.clear()
    h.register_tools()
    invocation = ProcedureInvocation(
        invocation_id=str(uuid4()), procedure_id="p", version_id="v"
    )

    from ze_agents.base_agent import BaseAgent
    from ze_agents.registry import agent, register_instance

    client = h.scripted_client(
        (None, [h.tc("s1", "send_email", to="ana", body="hi")]), ("Sent.", None)
    )

    async def _run(self, ctx: AgentContext) -> AgentResult:
        if ctx.procedure_invocation is None:
            ctx.procedure_invocation = invocation
        text, tcs = await self.agentic_loop(
            ctx, client, list(ctx.messages), system="s", tool_names=["send_email"]
        )
        return AgentResult(agent=self.name, response=text, tool_calls=tcs)

    cls = type(
        "_Sender",
        (BaseAgent,),
        {
            "name": "sender",
            "description": "s",
            "tools": ["send_email"],
            "run": _run,
            "enabled": True,
        },
    )
    agent(cls)
    register_instance("sender", cls())

    graph = h.compiled_graph([SubTask("sender", "go")])
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    paused = (await graph.aget_state(cfg)).values
    assert [i.invocation_id for i in paused["procedure_invocations"]] == [
        invocation.invocation_id
    ]

    out = await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)

    activator = SimpleNamespace(record_action=AsyncMock(), complete=AsyncMock())
    await complete_procedure_invocations(
        out, {"configurable": {"procedure_activator": activator}}
    )
    activator.complete.assert_awaited_once()
    assert activator.complete.await_args.kwargs["outcome"] is ProcedureOutcome.SUCCEEDED
    clear_tool_registry()


async def test_a_skipped_subtask_does_not_shift_the_result_an_invocation_closes_with(
    registry,
) -> None:
    from ze_agents.registry import get_agent_class
    from ze_core.orchestration.nodes.execution import execute_tool

    activator = SimpleNamespace(record_action=AsyncMock(), complete=AsyncMock())
    config = {"configurable": {"procedure_activator": activator}}
    _invoking_agent("a", [_bad("search_email")], invoke=False)
    _invoking_agent("b", [], invoke=False)
    ids = _invoking_agent("c", [_ok("send_email")])
    get_agent_class("b").enabled = False
    state = _turn_state(["a", "b", "c"])

    out = await execute_tool(state, config)

    [invocation] = out["procedure_invocations"]
    assert invocation.subtask == 2
    assert out["completed_subtask_indexes"] == [0, 2]
    await complete_procedure_invocations({**state, **out}, config)
    activator.complete.assert_awaited_once()
    assert str(activator.complete.await_args.args[0]) == ids["c"]
    assert activator.complete.await_args.kwargs["outcome"] is ProcedureOutcome.SUCCEEDED
