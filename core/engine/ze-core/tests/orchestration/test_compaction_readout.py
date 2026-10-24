"""B6 (phase 198): the compaction readout on a turn's trace matches the history
that turn's prompt was built from, checked across consecutive turns of one thread."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver
from ze_agents.base_agent import BaseAgent
from ze_agents.interface.types import RawInput
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.types import AgentContext, AgentResult
from ze_core.checkpoint_serde import build_checkpoint_serde
from ze_core.conversation.messages.types import CompactionTrace
from ze_core.conversation.turn import make_graph_input
from ze_core.orchestration.edges import after_decompose, after_embed_route
from ze_core.orchestration.graph import graph_builder
from ze_core.orchestration.nodes.context import fetch_context
from ze_core.orchestration.nodes.execution import execute_tool
from ze_core.orchestration.nodes.memory import write_memory
from ze_core.orchestration.nodes.trace import record_trace
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_memory.types import MemoryContext

BIG = "x" * 100_000


@pytest.fixture(autouse=True)
def registry():
    clear_registry()
    seen: list[list[dict]] = []

    class _Companion(BaseAgent):
        async def run(self, ctx: AgentContext) -> AgentResult:
            seen.append(list(ctx.messages))
            return AgentResult(agent="companion", response="ok")

    _Companion.name = "companion"
    _Companion.description = "companion"
    _Companion.enabled = True
    _Companion.timeout = 30
    agent(_Companion)
    register_instance("companion", object.__new__(_Companion))
    registry.prompts = seen
    yield
    clear_registry()


async def _noop(state, config):
    return {}


async def _embed_route(state, config):
    return {
        "envelope": RoutingEnvelope(
            primary_agent="companion",
            confidence=0.9,
            score_gap=0.3,
            routing_method="embedding",
            is_compound=False,
            subtasks=[
                SubTask(
                    agent="companion", prompt=state["prompt"], model="unknown/model"
                )
            ],
            requires_synthesis=False,
        )
    }


async def _fetch_context_on_small_window(state, config):
    update = await fetch_context(state, config)
    update["agent_context"].model = "unknown/model"  # the default 32k window
    return update


def _graph():
    overrides = {
        "preprocess": _noop,
        "embed_route": _embed_route,
        "decompose": _noop,
        "fetch_context": _fetch_context_on_small_window,
        "match_skills": _noop,
        "preflight": _noop,
        "execute_tool": execute_tool,
        "correlate": _noop,
        "surface_loops": _noop,
        "synthesize": _noop,
        "record_trace": record_trace,
        "write_memory": write_memory,
    }
    builder = graph_builder(node_overrides=overrides)
    builder.add_conditional_edges(
        "embed_route",
        after_embed_route,
        {"decompose": "decompose", "fetch_context": "fetch_context"},
    )
    builder.add_conditional_edges(
        "decompose", after_decompose, {"fetch_context": "fetch_context"}
    )
    return builder.compile(
        checkpointer=MemorySaver(serde=build_checkpoint_serde(plugins=[])),
        interrupt_before=["await_budget_confirmation", "await_write_confirmation"],
    )


def _config() -> dict:
    store = AsyncMock()
    store.retrieve = AsyncMock(return_value=MemoryContext())
    store.get_session_summary = AsyncMock(return_value=None)
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1, 0.2])
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=["condensed summary", "second summary"])
    return {
        "configurable": {
            "thread_id": "t1",
            "memory_store": store,
            "embedder": embedder,
            "openrouter_client": client,
            "settings": None,
            "persona_store": None,
            "person_store": None,
            "turn_surfacer": None,
            "fact_extractor": None,
        }
    }


def _long_history() -> list[dict]:
    return [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": BIG if i == 0 else f"m{i}",
        }
        for i in range(9)
    ]


async def _turn(graph, config, text: str):
    await graph.ainvoke(make_graph_input(RawInput(text=text), "t1"), config)
    return (await graph.aget_state(config)).values["message_trace"].compaction


def _opens_with_summary(messages: list[dict]) -> bool:
    return bool(messages) and bool(messages[0].get("compaction_summary"))


async def test_the_summary_stays_in_the_prompt_and_the_readout_says_so():
    graph = _graph()
    config = _config()
    await graph.aupdate_state(config, {"messages": _long_history()})

    readouts = [await _turn(graph, config, f"turn {n}") for n in range(1, 5)]

    assert [_opens_with_summary(p) for p in registry.prompts] == [
        False,
        True,
        True,
        True,
    ]
    assert readouts[0] is None
    for readout in readouts[1:]:
        assert readout == CompactionTrace(span_start=0, span_end=0)


async def test_a_second_compaction_replaces_the_summary_and_the_span():
    graph = _graph()
    config = _config()
    await graph.aupdate_state(config, {"messages": _long_history()})
    for n in range(1, 5):
        await _turn(graph, config, f"turn {n}")

    history = (await graph.aget_state(config)).values["messages"]
    history[1] = {**history[1], "content": BIG}
    await graph.aupdate_state(config, {"messages": history})
    await _turn(graph, config, "turn 5")  # compacts again after its reply
    readout = await _turn(graph, config, "turn 6")

    prompt = registry.prompts[-1]
    assert [m["content"] for m in prompt if m.get("compaction_summary")] == [
        "second summary"
    ]
    assert _opens_with_summary(prompt)
    assert readout == CompactionTrace(span_start=0, span_end=2)
