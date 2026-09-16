from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.types import AgentContext, AgentResult, GateDecision, ToolCall
from ze_core.conversation.messages.types import ProcedureUsageTrace
from ze_core.orchestration.nodes.context import fetch_context
from ze_core.orchestration.nodes.trace import record_trace
from ze_core.orchestration.procedure_activation import (
    complete_procedure_invocation,
    record_guided_actions,
)
from ze_memory.procedures.types import (
    CapabilityDecision,
    MatchState,
    ProcedureActionOutcome,
    ProcedureMatch,
    ProcedureOutcome,
)
from ze_memory.types import MemoryContext


def _match(**overrides) -> ProcedureMatch:
    base = dict(
        procedure_id=uuid4(),
        version_id=uuid4(),
        version_number=1,
        name="Inbox sweep",
        trigger="clear the morning inbox",
        steps=["open inbox"],
        state=MatchState.READY,
        matched_trigger="clear the morning inbox",
        satisfied_preconditions=["inbox is connected"],
        unmet_preconditions=[],
        effective_tool_names=frozenset({"search_email"}),
        procedure_relevant_tools=frozenset({"search_email"}),
    )
    base.update(overrides)
    return ProcedureMatch(**base)


def _config(discovery=None) -> dict:
    store = AsyncMock()
    store.retrieve = AsyncMock(return_value=MemoryContext())
    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=[0.1, 0.2])
    return {
        "configurable": {
            "memory_store": store,
            "embedder": embedder,
            "settings": None,
            "persona_store": None,
            "person_store": None,
            "procedure_discovery": discovery,
        }
    }


async def test_fetch_context_attaches_ready_and_blocked_guidance() -> None:
    ready = _match()
    blocked = _match(state=MatchState.BLOCKED, unmet_preconditions=["inbox is connected"])
    discovery = SimpleNamespace(match=AsyncMock(return_value=[ready, blocked]))
    result = await fetch_context(
        {
            "session_id": "s1",
            "prompt": "clear the morning inbox",
            "messages": [],
            "envelope": SimpleNamespace(
                subtasks=[SimpleNamespace(agent="companion", intent="read")]
            ),
        },
        _config(discovery),
    )
    ctx = result["agent_context"]
    assert ctx.procedure_matches == [ready, blocked]
    assert ctx.procedure_guidance is not None
    assert "ready" in ctx.procedure_guidance
    assert "blocked" in ctx.procedure_guidance
    assert "invoke_procedure" in ctx.procedure_guidance


async def test_fetch_context_without_discovery_keeps_prior_behavior() -> None:
    result = await fetch_context(
        {
            "session_id": "s1",
            "prompt": "hello",
            "messages": [],
        },
        _config(None),
    )
    ctx = result["agent_context"]
    assert ctx.prompt == "hello"
    assert ctx.procedure_matches is None
    assert ctx.procedure_guidance is None


async def test_fetch_context_discovers_for_any_routed_agent() -> None:
    """All graph agents share fetch_context; discovery is not per-agent wiring."""
    ready = _match()
    discovery = SimpleNamespace(match=AsyncMock(return_value=[ready]))
    for agent_name in ("companion", "research", "calendar", "email"):
        result = await fetch_context(
            {
                "session_id": "s1",
                "prompt": "clear the morning inbox",
                "messages": [],
                "envelope": SimpleNamespace(
                    subtasks=[SimpleNamespace(agent=agent_name, intent="read")]
                ),
            },
            _config(discovery),
        )
        assert result["agent_context"].procedure_matches == [ready]
