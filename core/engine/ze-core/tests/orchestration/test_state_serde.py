"""
Serialization smoke tests for AgentState.

LangGraph checkpoints the entire graph state to Postgres after every node using
JsonPlusSerializer + msgpack. These tests verify that a realistic AgentState —
as produced by fetch_context — survives a full dumps_typed → loads_typed
round-trip with the same serde configuration used in production.

A failure here means the app will crash at checkpoint time, not at startup,
which makes it hard to catch without exercising the full flow in dev.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer  # type: ignore[import]

from ze_memory.types import Episode, Fact, MemoryContext, ProfileFacet
from ze_agents.types import AgentContext, AgentResult, ToolCall
from ze_core.checkpoint_serde import build_checkpoint_serde
from ze_core.conversation.messages.types import (
    MemoryChunkTrace,
    MessageTrace,
    ToolCallTrace,
)
from ze_core.routing.types import RoutingEnvelope, SubTask


# ── Serde fixture ─────────────────────────────────────────────────────────────


@pytest.fixture
def serde() -> JsonPlusSerializer:
    return build_checkpoint_serde(plugins=[])


# ── Builders for realistic domain objects ─────────────────────────────────────


def _make_memory_context() -> MemoryContext:
    return MemoryContext(
        facts=[
            Fact(
                id=UUID("12345678-1234-5678-1234-567812345678"),
                subject_id=None,
                predicate="name",
                object_text=None,
                object_id=None,
                value="João",
                confidence=0.9,
                reviewed=True,
                embedding=None,
            )
        ],
        episodes=[
            Episode(
                id=UUID("87654321-4321-8765-4321-876543218765"),
                session_id="test-session",
                agent="research",
                prompt="what is the weather?",
                response="It is sunny.",
                summary="Weather query",
                relevance=0.7,
                created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                embedding=None,  # must be None in stored state
            )
        ],
        token_estimate=120,
        profile=[
            ProfileFacet(
                key="preferences",
                value="concise replies",
                stability="stable",
                confidence=0.9,
                updated_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
            )
        ],
    )


def _make_agent_context() -> AgentContext:
    return AgentContext(
        session_id="test-session",
        prompt="what is on my calendar today?",
        memory=_make_memory_context(),
        contacts=None,
        tool_calls=[
            ToolCall(
                tool_name="get_events",
                args={"date": "today"},
                result=[{"title": "standup"}],
                duration_ms=120,
                success=True,
            )
        ],
        messages=[{"role": "user", "content": "what is on my calendar today?"}],
        persona={"humor": 5, "verbosity": 3},
        model="openai/gpt-4o-mini",
        reporter=None,  # never serialized; must stay None in stored state
        extensions={},  # functions must never be stored here
    )


def _make_envelope() -> RoutingEnvelope:
    return RoutingEnvelope(
        primary_agent="calendar",
        confidence=0.92,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent="calendar", prompt="what is on my calendar today?")],
        requires_synthesis=False,
        raw_scores={"calendar": 0.92, "research": 0.62},
    )


def _make_agent_result() -> AgentResult:
    return AgentResult(
        agent="calendar",
        response="You have a standup at 10am.",
        tool_calls=[
            ToolCall(
                tool_name="get_events",
                args={"date": "today"},
                result=[{"title": "standup", "time": "10:00"}],
                duration_ms=85,
                success=True,
            )
        ],
        tokens_used=340,
    )


# ── Round-trip helpers ────────────────────────────────────────────────────────


def round_trip(serde: JsonPlusSerializer, obj: object) -> object:
    type_, data = serde.dumps_typed(obj)
    return serde.loads_typed((type_, data))


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_memory_context_round_trips(serde: JsonPlusSerializer) -> None:
    original = _make_memory_context()
    restored = round_trip(serde, original)
    assert restored.token_estimate == original.token_estimate
    assert restored.facts[0].predicate == "name"
    assert restored.facts[0].id == original.facts[0].id
    assert restored.episodes[0].agent == "research"
    assert restored.profile[0].key == "preferences"


def test_agent_context_round_trips(serde: JsonPlusSerializer) -> None:
    original = _make_agent_context()
    restored = round_trip(serde, original)
    assert restored.session_id == original.session_id
    assert restored.prompt == original.prompt
    assert restored.memory.facts[0].predicate == "name"
    assert restored.tool_calls[0].tool_name == "get_events"
    assert restored.extensions == {}
    assert restored.reporter is None


def test_routing_envelope_round_trips(serde: JsonPlusSerializer) -> None:
    original = _make_envelope()
    restored = round_trip(serde, original)
    assert restored.primary_agent == "calendar"
    assert restored.subtasks[0].agent == "calendar"
    assert restored.raw_scores["calendar"] == pytest.approx(0.92)


def test_agent_result_round_trips(serde: JsonPlusSerializer) -> None:
    original = _make_agent_result()
    restored = round_trip(serde, original)
    assert restored.agent == "calendar"
    assert restored.tokens_used == 340
    assert restored.tool_calls[0].success is True


def test_full_agent_state_dict_round_trips(serde: JsonPlusSerializer) -> None:
    """Mirrors what LangGraph checkpoints: the entire state dict value by value."""
    state = {
        "prompt": "what is on my calendar today?",
        "session_id": "test-session",
        "input_modality": "text",
        "voice_input": None,
        "image_data": None,
        "image_mime": None,
        "image_caption": None,
        "envelope": _make_envelope(),
        "memory_context": _make_memory_context(),
        "agent_context": _make_agent_context(),
        "agent_result": _make_agent_result(),
        "subtask_results": [_make_agent_result()],
        "completed_subtask_indexes": [0],
        "blocked": False,
        "parked_subtasks": [],
        "write_confirmation": None,
        "write_decisions": [],
        "write_rounds": 0,
        "write_outcomes": [],
        "messages": [{"role": "user", "content": "what is on my calendar today?"}],
        "last_active_at": 1_700_000_000.0,
        "final_response": "You have a standup at 10am.",
        "error": None,
        "conductor_hint": None,
        "conductor_ledger": [],
        "conductor_delegate_counts": {},
        "conductor_delegate_total": 0,
        "message_trace": MessageTrace(
            agent="calendar",
            routing_method="embedding",
            confidence=0.92,
            score_gap=0.30,
            is_compound=False,
            subtasks=["calendar"],
            memory_chunks=[
                MemoryChunkTrace(text="name: João", score=0.9, source="fact")
            ],
            tool_calls=[
                ToolCallTrace(
                    name="get_events",
                    result_snippet="standup",
                    duration_ms=85,
                    success=True,
                )
            ],
            tool_duration_ms=85,
        ),
    }

    for key, value in state.items():
        try:
            restored = round_trip(serde, value)
        except Exception as exc:
            pytest.fail(f"State field {key!r} failed serde round-trip: {exc}")

        assert restored == value or restored is value, (
            f"State field {key!r} did not survive round-trip: {value!r} → {restored!r}"
        )


def test_non_serializable_embed_fn_raises(serde: JsonPlusSerializer) -> None:
    ctx = AgentContext(
        session_id="s",
        prompt="p",
        embed_fn=lambda _text: [0.1],
    )
    with pytest.raises((TypeError, Exception)):
        serde.dumps_typed(ctx)


def test_non_serializable_identity_builder_raises(serde: JsonPlusSerializer) -> None:
    """Regression: AgentContext with identity_builder set must not be checkpointed.

    identity_builder is a runtime-only callable. Stored contexts always have it
    as None. If someone accidentally checkpoints a context with it set, the serde
    must fail loudly here in CI rather than at runtime in production.
    """

    def _some_builder(
        persona: dict, memory_context: str, *, profile: Any, contacts_context: str
    ) -> str:
        return "identity"

    ctx = AgentContext(
        session_id="s",
        prompt="p",
        identity_builder=_some_builder,
    )
    with pytest.raises((TypeError, Exception)):
        serde.dumps_typed(ctx)


def test_trace_with_telemetry_fields_round_trips(serde: JsonPlusSerializer) -> None:
    from ze_core.conversation.messages.types import (
        JudgmentBar,
        JudgmentTrace,
        ModelUsage,
        RoutingScore,
        RoutingThresholds,
        StageTiming,
        TurnUsage,
    )

    trace = MessageTrace(
        agent="calendar",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.2,
        is_compound=False,
        subtasks=["calendar"],
        tool_calls=[
            ToolCallTrace(
                name="list_events",
                result_snippet="x",
                duration_ms=12,
                success=True,
                call_id="abc",
                start_offset_ms=640,
            )
        ],
        judgments=[
            JudgmentTrace(
                question_id="agent",
                kind="choice",
                latency_ms=5,
                surface="routing",
                bar=JudgmentBar("choice_trust", 0.5),
            )
        ],
        tool_duration_ms=12,
        turn_duration_ms=2140,
        paused_ms=20000,
        stages=[StageTiming("fetch_context", 212, 88, 1)],
        usage=TurnUsage(
            main_model="m",
            models=[ModelUsage("m", 2, 9120, 410, 5200, 0.03, False)],
            context_fill=0.026,
            context_window=200000,
            system_one_tokens=1840,
        ),
        routing_scores=[RoutingScore("calendar", 0.83)],
        routing_thresholds=RoutingThresholds(0.78, 0.05),
        telemetry_partial=True,
    )
    assert round_trip(serde, trace) == trace


def test_parked_loop_keeps_call_id_and_started_at(serde: JsonPlusSerializer) -> None:
    from ze_agents.park import ParkedLoop, ParkedWrite

    call = ToolCall(
        tool_name="list_events",
        args={},
        result="ok",
        duration_ms=3,
        success=True,
        call_id="fixed-id",
        started_at=1234.5,
    )
    write = ParkedWrite(
        item_id="i",
        call_id="call_0",
        tool="send",
        args={},
        effect_phrase="sent",
        summary="s",
        agent="messenger",
        trace_call_id="trace-id",
    )
    loop = ParkedLoop(
        agent="messenger",
        messages=[],
        accumulated=[call],
        iteration=1,
        parked=[write],
    )
    restored = round_trip(serde, loop)
    assert restored == loop
    assert restored.accumulated[0].call_id == "fixed-id"
    assert restored.accumulated[0].started_at == 1234.5
    assert restored.parked[0].trace_call_id == "trace-id"


def test_script_step_round_trips_through_a_parked_loop(serde: JsonPlusSerializer) -> None:
    from ze_agents.park import ParkedLoop

    inner = ToolCall(
        tool_name="get_transactions",
        args={"period": "month"},
        result="[]",
        duration_ms=2,
        success=True,
        parent_call_id="step-1",
    )
    step = ToolCall(
        tool_name="run_tool_script",
        args={"source_hash": "abc"},
        result="{}",
        duration_ms=9,
        success=True,
        call_id="step-1",
        inner_calls=[inner],
        script={"source": "x=1", "source_cut": False, "outcome": "ok", "limit": None,
                "source_hash": "abc", "procedure_id": None},
    )
    loop = ParkedLoop(
        agent="finance", messages=[], accumulated=[step], iteration=1, parked=[]
    )
    restored = round_trip(serde, loop)
    assert restored == loop
    assert restored.accumulated[0].inner_calls[0].parent_call_id == "step-1"
    assert restored.accumulated[0].script["outcome"] == "ok"


def test_agent_context_with_a_script_runner_is_never_the_stored_shape() -> None:
    ctx = AgentContext(session_id="s", prompt="p")
    assert ctx.script_runner is None


def test_context_parts_round_trip(serde: JsonPlusSerializer) -> None:
    from ze_agents.types import (
        ConductorState,
        DelegateTally,
        ProcedureInvocation,
        WriteGateState,
    )

    ctx = AgentContext(
        session_id="s",
        prompt="p",
        conductor=ConductorState(
            hint=[{"agent": "calendar", "prompt": "x"}],
            ledger=[{"agent": "calendar", "status": "done"}],
            tally=DelegateTally(counts={"calendar": 1}, total=1),
        ),
        procedure_invocation=ProcedureInvocation(
            invocation_id="i", procedure_id="p", version_id="v", tool_names=["a"], subtask=2
        ),
        write_gate=WriteGateState(
            pre_approved=frozenset({"send_email"}), round=1, retry_mode=True
        ),
    )
    restored = round_trip(serde, ctx)
    assert restored == ctx
