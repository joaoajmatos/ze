from unittest.mock import AsyncMock, MagicMock, patch

from ze_agents.types import AgentContext, AgentResult, ToolCall
from ze_core.orchestration.nodes.memory import write_memory
from ze_memory.types import Fact, MemoryContext


def _ctx(prompt: str = "hello") -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt=prompt,
        intent="read",
        memory=MemoryContext(),
        messages=[],
    )


def _config(store, fact_extractor) -> dict:
    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=[0.1, 0.2])
    return {
        "configurable": {
            "memory_store": store,
            "embedder": embedder,
            "thread_id": "s1",
            "fact_extractor": fact_extractor,
        }
    }


def _remember_call(*, ok: bool, predicate: str, value: str, success: bool = True):
    return ToolCall(
        tool_name="remember_fact",
        args={"predicate": predicate, "value": value},
        result={"ok": ok},
        duration_ms=1,
        success=success,
    )


async def test_extractor_duplicate_same_identity_is_skipped():
    store = AsyncMock()
    store.write_episode = AsyncMock()

    async def extractor(_cfg, **_kwargs):
        return [Fact(predicate="preference", value="dark mode")]

    state = {
        "session_id": "s1",
        "agent_context": _ctx("Remember I prefer dark mode."),
        "agent_result": AgentResult(
            agent="companion",
            response="I'll remember that.",
            tool_calls=[
                _remember_call(ok=True, predicate="preference", value="dark mode")
            ],
        ),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
    }
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        await write_memory(state, _config(store, extractor))
    submit.assert_not_awaited()


async def test_extractor_may_write_a_different_identity():
    store = AsyncMock()
    store.write_episode = AsyncMock()

    async def extractor(_cfg, **_kwargs):
        return [
            Fact(predicate="preference", value="dark mode"),
            Fact(predicate="preference", value="aisle seats"),
        ]

    state = {
        "session_id": "s1",
        "agent_context": _ctx("Remember dark mode. I also like aisle seats."),
        "agent_result": AgentResult(
            agent="companion",
            response="Got it",
            tool_calls=[
                _remember_call(ok=True, predicate="preference", value="dark mode")
            ],
        ),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
    }
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        await write_memory(state, _config(store, extractor))
    facts = [item.fact for item in submit.await_args.args[1]]
    assert [(f.predicate, f.value) for f in facts] == [("preference", "aisle seats")]


async def test_failed_remember_is_not_a_second_remember_door():
    store = AsyncMock()
    store.write_episode = AsyncMock()

    async def extractor(_cfg, **_kwargs):
        return [Fact(predicate="preference", value="dark mode")]

    state = {
        "session_id": "s1",
        "agent_context": _ctx("Remember I prefer dark mode."),
        "agent_result": AgentResult(
            agent="companion",
            response="I'll remember that.",
            tool_calls=[
                _remember_call(ok=False, predicate="preference", value="dark mode")
            ],
        ),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
    }
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        await write_memory(state, _config(store, extractor))
    facts = [item.fact for item in submit.await_args.args[1]]
    assert [(f.predicate, f.value) for f in facts] == [("preference", "dark mode")]


async def test_admission_judgments_land_on_recorded_trace():
    from ze_core.conversation.messages.types import MessageTrace

    row = {
        "question_id": "speech_act",
        "kind": "choice",
        "latency_ms": 80,
        "answer": "reminder",
        "probabilities": None,
        "peakedness": 0.9,
        "model": "typesafe/jev-1.13",
        "input_tokens": 40,
        "consumed": True,
        "skip_reason": None,
    }

    async def extractor(cfg, **_kwargs):
        cfg["admission_judgments"].append(row)
        return []

    trace = MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.8,
        score_gap=0.1,
        is_compound=False,
        subtasks=["companion"],
    )
    state = {
        "session_id": "s1",
        "agent_context": _ctx("remind me Tuesday"),
        "agent_result": AgentResult(agent="companion", response="ok"),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
        "message_trace": trace,
    }
    store = AsyncMock()
    store.write_episode = AsyncMock()
    await write_memory(state, _config(store, extractor))
    assert [j.answer for j in trace.judgments] == ["reminder"]
    assert trace.judgments[0].consumed is True
