from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.types import AgentContext, AgentResult, GateDecision, ToolCall
from ze_core.conversation.messages.types import ProcedureUsageTrace
from ze_core.orchestration.nodes.trace import record_trace
from ze_core.orchestration.procedure_activation import (
    complete_procedure_invocation,
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
    ctx = AgentContext(
        session_id="s1",
        prompt="clear inbox",
        intent="execute",
        gate_decision=GateDecision.BLOCKED,
        procedure_invocation_id=str(invocation_id),
        procedure_invoked_id=str(uuid4()),
        procedure_invoked_version_id=str(uuid4()),
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
                error="Tool 'search_email' is blocked by the capability gate",
            )
        ],
    )
    await record_guided_actions(
        ctx, result, {"configurable": {"procedure_activator": activator}}
    )
    kwargs = activator.record_action.await_args.kwargs
    assert kwargs["capability_decision"] is CapabilityDecision.DENIED
    assert kwargs["outcome"] is ProcedureActionOutcome.NOT_EXECUTED


async def test_complete_is_forwarded_once() -> None:
    activator = SimpleNamespace(complete=AsyncMock())
    invocation_id = uuid4()
    ctx = AgentContext(
        session_id="s1",
        prompt="clear inbox",
        intent="execute",
        procedure_invocation_id=str(invocation_id),
    )
    result = AgentResult(
        agent="companion",
        response="done",
        tool_calls=[
            ToolCall(tool_name="search_email", args={}, result="ok", duration_ms=1, success=True)
        ],
    )
    await complete_procedure_invocation(
        ctx, result, {"configurable": {"procedure_activator": activator}}
    )
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
        "agent_context": AgentContext(
            session_id="s1",
            prompt="hi",
            intent="read",
            procedure_invocation_id=str(invocation_id),
            procedure_invoked_id=str(procedure_id),
            procedure_invoked_version_id=str(version_id),
        ),
    }
    result = await record_trace(state, {"configurable": {}})
    assert result["message_trace"].procedure == ProcedureUsageTrace(
        invocation_id=str(invocation_id),
        procedure_id=str(procedure_id),
        version_id=str(version_id),
    )
