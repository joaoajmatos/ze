"""Message-trace serialization for procedure-guided actions (Phase 139 US3)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from ze_agents.types import AgentContext, AgentResult
from ze_core.conversation.messages.types import ProcedureUsageTrace
from ze_core.orchestration.nodes.trace import record_trace


async def test_record_trace_serializes_procedure_invocation_ids() -> None:
    invocation_id = uuid4()
    procedure_id = uuid4()
    version_id = uuid4()
    result = await record_trace(
        {
            "envelope": SimpleNamespace(
                primary_agent="companion",
                routing_method="embedding",
                confidence=0.8,
                score_gap=0.2,
                is_compound=False,
                subtasks=[],
            ),
            "agent_result": AgentResult(agent="companion", response="ok"),
            "agent_context": AgentContext(
                session_id="s1",
                prompt="clear inbox",
                intent="execute",
                procedure_invocation_id=str(invocation_id),
                procedure_invoked_id=str(procedure_id),
                procedure_invoked_version_id=str(version_id),
            ),
        },
        {"configurable": {}},
    )
    procedure = result["message_trace"].procedure
    assert procedure == ProcedureUsageTrace(
        invocation_id=str(invocation_id),
        procedure_id=str(procedure_id),
        version_id=str(version_id),
    )


async def test_record_trace_omits_procedure_when_not_invoked() -> None:
    result = await record_trace(
        {
            "envelope": SimpleNamespace(
                primary_agent="companion",
                routing_method="embedding",
                confidence=0.8,
                score_gap=0.2,
                is_compound=False,
                subtasks=[],
            ),
            "agent_result": AgentResult(agent="companion", response="ok"),
            "agent_context": AgentContext(
                session_id="s1", prompt="hello", intent="read"
            ),
        },
        {"configurable": {}},
    )
    assert result["message_trace"].procedure is None


async def test_record_trace_copies_conductor_ledger() -> None:
    hint = [{"agent": "calendar", "intent": "read", "prompt": "tue"}]
    ledger = [{"agent": "calendar", "status": "done"}]
    result = await record_trace(
        {
            "envelope": SimpleNamespace(
                primary_agent="companion",
                routing_method="haiku",
                confidence=0.8,
                score_gap=0.2,
                is_compound=False,
                subtasks=[],
            ),
            "agent_result": AgentResult(agent="companion", response="ok"),
            "conductor_hint": hint,
            "conductor_ledger": ledger,
            "agent_context": AgentContext(
                session_id="s1", prompt="hello", intent="reason"
            ),
        },
        {"configurable": {}},
    )
    trace = result["message_trace"]
    assert trace.conductor_hint == hint
    assert trace.conductor_ledger == ledger
