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
                session_id="s1",
                prompt="hello",
            ),
        },
        {"configurable": {}},
    )
    assert result["message_trace"].procedure is None


async def test_record_trace_copies_conductor_ledger() -> None:
    hint = [{"agent": "calendar", "prompt": "tue"}]
    ledger = [
        {"agent": "calendar", "status": "stalled"},
        {"agent": "calendar", "status": "replanned"},
        {"agent": "calendar", "status": "ask_user"},
    ]
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
                session_id="s1",
                prompt="hello",
            ),
        },
        {"configurable": {}},
    )
    trace = result["message_trace"]
    assert trace.conductor_hint == hint
    assert trace.conductor_ledger == ledger


async def test_record_trace_marks_promote_offered_on_unfinished_close() -> None:
    ledger = [
        {"agent": "research", "status": "done"},
        {"agent": "messenger", "status": "planned"},
    ]
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
            "conductor_ledger": ledger,
            "agent_context": AgentContext(
                session_id="s1",
                prompt="hello",
            ),
        },
        {"configurable": {}},
    )
    statuses = [e["status"] for e in result["message_trace"].conductor_ledger]
    assert "promote_offered" in statuses


def test_skill_usage_trace_below_floor_defaults_false():
    from ze_core.conversation.messages.types import SkillUsageTrace

    t = SkillUsageTrace(skill_id="1", name="a", source="imported", trigger="automatic")
    assert t.below_floor is False


def test_old_stored_trace_without_below_floor_parses_with_default():
    from ze_core.conversation.messages.store import _parse_trace

    trace = _parse_trace(
        {
            "agent": "a",
            "routing_method": "embedding",
            "confidence": 1.0,
            "score_gap": 0.0,
            "is_compound": False,
            "skills_used": [
                {
                    "skill_id": "1",
                    "name": "a",
                    "source": "imported",
                    "trigger": "automatic",
                    "similarity": 0.6,
                }
            ],
        }
    )
    assert trace.skills_used[0].below_floor is False


# ── Phase 165: effect metadata on tool calls ─────────────────────────────────

import pytest  # noqa: E402
from ze_agents.reversibility import ToolReversibility  # noqa: E402
from ze_agents.tool import ToolAccess, clear_tool_registry, tool  # noqa: E402
from ze_agents.types import ToolCall  # noqa: E402
from ze_core.conversation.messages.store import _parse_trace  # noqa: E402


@pytest.fixture
def effect_tools():
    clear_tool_registry()

    @tool(access=ToolAccess.READ, description="r")
    async def lookup() -> str: ...

    @tool(
        access=ToolAccess.WRITE,
        description="w",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
    )
    async def send_email() -> str: ...

    @tool(
        access=ToolAccess.WRITE,
        description="w",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="send_email",
        undo_note="n",
        effect_phrase="set a reminder",
    )
    async def set_reminder() -> str: ...

    yield
    clear_tool_registry()


def _state(result, **extra) -> dict:
    return {
        "envelope": SimpleNamespace(
            primary_agent="companion",
            routing_method="embedding",
            confidence=0.8,
            score_gap=0.2,
            is_compound=False,
            subtasks=[],
        ),
        "agent_result": result,
        "agent_context": AgentContext(
            session_id="s1",
            prompt="x",
        ),
        **extra,
    }


def _call(name: str, **kw) -> ToolCall:
    return ToolCall(
        tool_name=name, args={}, result="ok", duration_ms=1, success=True, **kw
    )


async def test_record_trace_resolves_effect_metadata(effect_tools) -> None:
    result = AgentResult(
        agent="companion",
        response="ok",
        tool_calls=[_call("lookup"), _call("set_reminder"), _call("mystery")],
    )
    trace = (await record_trace(_state(result), {"configurable": {}}))["message_trace"]
    by_name = {t.name: t for t in trace.tool_calls}
    assert trace.effects_known is True
    assert by_name["lookup"].access == "read"
    assert by_name["lookup"].reversibility is None
    assert by_name["set_reminder"].access == "write"
    assert by_name["set_reminder"].reversibility == "reversible"
    assert by_name["set_reminder"].undo_tool == "send_email"
    assert by_name["set_reminder"].effect_phrase == "set a reminder"
    assert by_name["mystery"].access == "unknown"


async def test_record_trace_flattens_nested_delegate_send(effect_tools) -> None:
    delegate = ToolCall(
        tool_name="delegate_to_agent",
        args={},
        result={
            "response": "sent",
            "tool_calls": [
                {
                    "tool_name": "send_email",
                    "args": {},
                    "result": "ok",
                    "duration_ms": 1,
                    "success": True,
                    "gate": "approved",
                }
            ],
        },
        duration_ms=1,
        success=True,
        gate="approved",
    )
    result = AgentResult(agent="companion", response="ok", tool_calls=[delegate])
    trace = (await record_trace(_state(result), {"configurable": {}}))["message_trace"]
    by_name = {t.name: t for t in trace.tool_calls}
    assert by_name["delegate_to_agent"].access == "delegate"
    assert by_name["send_email"].access == "write"
    assert by_name["send_email"].reversibility == "irreversible"
    assert by_name["send_email"].gate == "approved"


async def test_record_trace_includes_compound_subtask_calls(effect_tools) -> None:
    sub = AgentResult(
        agent="messenger",
        response="ok",
        tool_calls=[_call("send_email", gate="approved")],
    )
    state = _state(None, subtask_results=[sub])
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    assert [t.name for t in trace.tool_calls] == ["send_email"]
    assert trace.tool_calls[0].gate == "approved"


async def test_a_read_call_keeps_the_none_gate(effect_tools) -> None:
    result = AgentResult(agent="companion", response="ok", tool_calls=[_call("lookup")])
    state = _state(result)
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    assert trace.tool_calls[0].gate == "none"


def test_old_trace_parses_as_effects_unknown() -> None:
    old = {
        "agent": "research",
        "routing_method": "embedding",
        "confidence": 0.9,
        "score_gap": 0.1,
        "is_compound": False,
        "subtasks": [],
        "tool_calls": [
            {"name": "web", "result_snippet": "", "duration_ms": 3, "success": True}
        ],
    }
    trace = _parse_trace(old)
    assert trace.effects_known is False
    assert trace.tool_calls[0].access == "unknown"
    assert trace.tool_calls[0].gate == "none"


def test_new_trace_round_trips_effect_fields() -> None:
    from dataclasses import asdict

    from ze_core.conversation.messages.types import MessageTrace, ToolCallTrace

    trace = MessageTrace(
        agent="a",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
        tool_calls=[
            ToolCallTrace(
                name="send_email",
                result_snippet="",
                duration_ms=1,
                success=True,
                access="write",
                reversibility="irreversible",
                gate="approved",
                effect_phrase="sent an email",
            )
        ],
        effects_known=True,
    )
    assert _parse_trace(asdict(trace)) == trace


async def test_only_the_approved_call_is_labelled_approved(
    effect_tools,
) -> None:
    approved = AgentResult(
        agent="messenger",
        response="ok",
        tool_calls=[_call("send_email", gate="approved")],
    )
    autonomous = AgentResult(
        agent="calendar", response="ok", tool_calls=[_call("set_reminder")]
    )
    state = _state(None, subtask_results=[approved, autonomous])
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    gates = {t.name: t.gate for t in trace.tool_calls}
    assert gates == {"send_email": "approved", "set_reminder": "none"}


async def test_openrouter_server_tools_are_known_reads(effect_tools) -> None:
    result = AgentResult(
        agent="research", response="ok", tool_calls=[_call("openrouter:web_search")]
    )
    trace = (await record_trace(_state(result), {"configurable": {}}))["message_trace"]
    assert trace.tool_calls[0].access == "read"


async def test_retry_refused_write_is_not_recorded_as_an_action(effect_tools) -> None:
    from ze_agents.base_agent import BaseAgent

    class _A(BaseAgent):
        name = "companion"
        description = "d"
        tools = []

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

    ctx = AgentContext(session_id="s", prompt="p", retry_mode=True)
    refused = await _A().call_tool("send_email", ctx)
    result = AgentResult(agent="companion", response="ok", tool_calls=[refused])
    trace = (await record_trace(_state(result), {"configurable": {}}))["message_trace"]
    assert trace.tool_calls[0].gate == "denied"


async def test_web_search_turn_stays_retryable(effect_tools) -> None:
    from datetime import datetime, timezone

    from ze_core.conversation.messages.types import Message
    from ze_core.conversation.retry import retry_eligibility

    result = AgentResult(
        agent="research", response="ok", tool_calls=[_call("openrouter:web_search")]
    )
    trace = (await record_trace(_state(result), {"configurable": {}}))["message_trace"]
    msg = Message(
        id=uuid4(),
        role="assistant",
        text="ok",
        components=[],
        read=True,
        created_at=datetime.now(timezone.utc),
        thread_id="t1",
    )
    eligibility = retry_eligibility(msg, trace, latest_assistant_id=msg.id)
    assert eligibility.available is True


async def test_record_trace_collects_deduped_sources_from_all_results():
    from ze_agents.types import Source

    main = AgentResult(
        agent="companion", response="ok", sources=[Source("https://a.test", "A")]
    )
    sub = AgentResult(
        agent="research",
        response="ok",
        sources=[Source("https://a.test", "A"), Source("https://b.test", "B")],
    )
    state = _state(main, subtask_results=[sub])
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    assert [(s.url, s.title) for s in trace.sources] == [
        ("https://a.test", "A"),
        ("https://b.test", "B"),
    ]


def test_sources_round_trip_through_stored_trace_and_old_traces_default_empty():
    from dataclasses import asdict

    from ze_core.conversation.messages.store import _parse_trace
    from ze_core.conversation.messages.types import MessageTrace, SourceTrace

    trace = MessageTrace(
        agent="research",
        routing_method="embedding",
        confidence=1.0,
        score_gap=0.0,
        is_compound=False,
        subtasks=[],
        sources=[SourceTrace(url="https://a.test", title="A")],
    )
    parsed = _parse_trace(asdict(trace))
    assert parsed.sources == trace.sources
    legacy = asdict(trace)
    del legacy["sources"]
    assert _parse_trace(legacy).sources == []


# ── Phase 171: loop offers on the trace ──────────────────────────────────────


def test_stored_trace_round_trips_loop_offer_ids():
    base = {
        "agent": "a",
        "routing_method": "embedding",
        "confidence": 1.0,
        "score_gap": 0.0,
        "is_compound": False,
    }
    assert _parse_trace({**base, "loop_offer_ids": ["abc"]}).loop_offer_ids == ["abc"]
    assert _parse_trace(base).loop_offer_ids == []


async def test_write_outcomes_are_copied_to_the_trace(effect_tools) -> None:
    rows = [
        {
            "request_id": "r1",
            "round": 1,
            "item_id": "i1",
            "agent": "messenger",
            "tool": "send_email",
            "effect": "send an email",
            "summary": "to: ana",
            "outcome": "denied",
        }
    ]
    result = AgentResult(agent="companion", response="ok", tool_calls=[])
    state = _state(result, write_outcomes=rows)
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    assert trace.write_confirmations == rows


async def test_pre_approved_call_gate_survives_to_the_trace(effect_tools) -> None:
    result = AgentResult(
        agent="messenger",
        response="ok",
        tool_calls=[_call("send_email", gate="pre_approved")],
    )
    trace = (await record_trace(_state(result), {"configurable": {}}))["message_trace"]
    assert trace.tool_calls[0].gate == "pre_approved"
