"""write_memory — consumes FactAdmission and merges judgments into message_trace."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext, AgentResult, ToolCall
from ze_core.conversation.messages.types import JudgmentTrace, MessageTrace
from ze_core.orchestration.nodes.memory import write_memory
from ze_memory.types import Fact, FactAdmission, MemoryContext


def _ctx(prompt: str = "I prefer aisle seats") -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt=prompt,
        intent="read",
        memory=MemoryContext(),
        messages=[],
    )


def _config(extractor, *, thread_id: str = "s1") -> dict:
    store = AsyncMock()
    store.write_episode = AsyncMock()
    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=[0.1, 0.2])
    return {
        "configurable": {
            "memory_store": store,
            "embedder": embedder,
            "thread_id": thread_id,
            "fact_extractor": extractor,
        }
    }


def _trace(judgments=None) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.3,
        is_compound=False,
        subtasks=[],
        judgments=list(judgments or []),
    )


def _state(trace, prompt: str = "I prefer aisle seats", tool_calls=None) -> dict:
    return {
        "session_id": "s1",
        "agent_context": _ctx(prompt),
        "agent_result": AgentResult(
            agent="companion", response="Noted.", tool_calls=tool_calls or []
        ),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
        "message_trace": trace,
    }


def _ok_result() -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="jev",
        input_tokens=10,
        latency_ms=5,
        answers={
            "speech_act": SystemOneAnswer(
                type="choice", choice="fact", confidence=0.9, probabilities={"fact": 0.9}
            ),
            "family": SystemOneAnswer(
                type="choice",
                choice="preference",
                confidence=0.9,
                probabilities={"preference": 0.9},
            ),
            "biography": SystemOneAnswer(type="noul", noul=0.9),
        },
    )


_IDS = ("speech_act", "family", "biography")


def _persist_admission(facts=None) -> FactAdmission:
    return FactAdmission(
        facts=facts if facts is not None else [Fact(predicate="preference", value="aisle seats")],
        path="system_one",
        judgment=_ok_result(),
        question_ids=_IDS,
        consumed=frozenset(_IDS),
    )


async def _run(admission, trace, **kw):
    async def extractor(_cfg, **_kwargs):
        return admission

    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        out = await write_memory(_state(trace, **kw), _config(extractor))
    return out, submit


async def test_submits_admission_facts():
    out, submit = await _run(_persist_admission(), _trace())
    facts = [i.fact for i in submit.await_args.args[1]]
    assert [(f.predicate, f.value) for f in facts] == [("preference", "aisle seats")]


async def test_no_judgment_leaves_trace_unchanged():
    admission = FactAdmission(facts=[], path="haiku")
    out, _ = await _run(admission, _trace())
    assert "message_trace" not in out


async def test_ok_judgment_appends_rows_after_existing():
    existing = JudgmentTrace(question_id="routing", kind="choice", latency_ms=1)
    trace = _trace([existing])
    out, _ = await _run(_persist_admission(), trace)
    rows = out["message_trace"].judgments
    assert rows[0] is existing
    assert [r.question_id for r in rows[1:]] == list(_IDS)
    assert all(r.consumed for r in rows[1:])
    assert trace.judgments == [existing]


async def test_trace_merge_also_in_compaction_branch():
    async def extractor(_cfg, **_kwargs):
        return _persist_admission()

    state = _state(_trace())
    state["messages"] = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
        for i in range(60)
    ]
    config = _config(extractor)
    config["configurable"]["openrouter_client"] = AsyncMock()
    config["configurable"]["openrouter_client"].complete = AsyncMock(return_value="sum")
    with (
        patch(
            "ze_core.orchestration.nodes.memory.submit_perception_facts",
            new_callable=AsyncMock,
        ),
        patch("ze_core.orchestration.nodes.memory._should_compact", return_value=True),
    ):
        out = await write_memory(state, config)
    assert out["compaction_span"] is not None
    assert len(out["message_trace"].judgments) == 3


async def test_missing_message_trace_does_not_crash():
    out, submit = await _run(_persist_admission(), None)
    assert "message_trace" not in out
    submit.assert_awaited_once()


async def test_eval_thread_never_calls_extractor():
    extractor = AsyncMock()
    state = _state(_trace())
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ):
        out = await write_memory(state, _config(extractor, thread_id="eval-1"))
    extractor.assert_not_awaited()
    assert "message_trace" not in out


async def test_skip_path_admission_has_no_duplicate_identity_and_skip_rows():
    skip = SystemOneResult(outcome="skip", skip_reason="timeout", latency_ms=2000)
    admission = FactAdmission(
        facts=[
            Fact(predicate="preference", value="aisle seats"),
            Fact(predicate="preference", value="window"),
        ],
        path="haiku",
        judgment=skip,
        question_ids=_IDS,
        skip_reason="timeout",
    )
    remembered = ToolCall(
        tool_name="remember_fact",
        args={"predicate": "preference", "value": "aisle seats"},
        result={"ok": True},
        duration_ms=1,
        success=True,
    )
    out, submit = await _run(admission, _trace(), tool_calls=[remembered])
    facts = [i.fact for i in submit.await_args.args[1]]
    assert [(f.predicate, f.value) for f in facts] == [("preference", "window")]
    rows = out["message_trace"].judgments
    assert [r.question_id for r in rows] == list(_IDS)
    assert all(not r.consumed and r.skip_reason == "timeout" for r in rows)
