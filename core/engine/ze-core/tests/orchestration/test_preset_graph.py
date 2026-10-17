"""Preset composition inside the real graph: fetch_context -> execute_tool on one thread."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver
from ze_agents.base_agent import BaseAgent
from ze_agents.interface.types import RawInput
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.types import AgentContext, AgentResult
from ze_core.checkpoint_serde import build_checkpoint_serde
from ze_core.conversation.turn import make_graph_input
from ze_core.orchestration.graph import graph_builder
from ze_core.orchestration.nodes.context import fetch_context
from ze_core.orchestration.nodes.execution import execute_tool
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_memory.types import MemoryContext

SLIPPING = [{"type": "headline", "text": "1 SLIPPING"}]


@pytest.fixture(autouse=True)
def registry():
    clear_registry()
    seen: list = []

    class _Companion(BaseAgent):
        async def run(self, ctx: AgentContext) -> AgentResult:
            seen.append(ctx.preset)
            return AgentResult(agent="companion", response="ok")

    _Companion.name = "companion"
    _Companion.description = "companion"
    _Companion.enabled = True
    _Companion.timeout = 30
    agent(_Companion)
    register_instance("companion", object.__new__(_Companion))
    registry.seen = seen
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
            subtasks=[SubTask(agent="companion", prompt=state["prompt"], model="m")],
            requires_synthesis=False,
        )
    }


def _graph():
    overrides = {
        "preprocess": _noop,
        "embed_route": _embed_route,
        "decompose": _noop,
        "fetch_context": fetch_context,
        "match_skills": _noop,
        "preflight": _noop,
        "execute_tool": execute_tool,
        "correlate": _noop,
        "surface_loops": _noop,
        "synthesize": _noop,
        "record_trace": _noop,
        "write_memory": _noop,
    }
    from ze_core.orchestration.edges import after_decompose, after_embed_route

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


def _config(*, screen_context=None, composer=None) -> dict:
    store = AsyncMock()
    store.retrieve = AsyncMock(return_value=MemoryContext())
    store.get_session_summary = AsyncMock(return_value=None)
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1, 0.2])
    return {
        "configurable": {
            "thread_id": "t1",
            "memory_store": store,
            "embedder": embedder,
            "settings": None,
            "persona_store": None,
            "person_store": None,
            "turn_surfacer": None,
            "world_composer": composer,
            "screen_context": screen_context,
        }
    }


def _composer():
    composer = AsyncMock()
    composer.compose_slipping = AsyncMock(
        return_value=SimpleNamespace(components=list(SLIPPING), summary="1 slipping")
    )
    return composer


def _input(text="What's slipping?"):
    return make_graph_input(RawInput(text=text), "s1")


async def test_a_plain_turn_after_a_preset_turn_has_no_preset_cards():
    graph = _graph()
    composer = _composer()
    preset = _config(
        screen_context={"screen": "world", "compose": "slipping"}, composer=composer
    )
    await graph.ainvoke(_input(), preset)
    first = (await graph.aget_state(preset)).values
    assert first["components"] == SLIPPING
    assert first["preset_components"] == SLIPPING

    plain = _config(composer=composer)
    await graph.ainvoke(_input("thanks"), plain)
    second = (await graph.aget_state(plain)).values
    assert second["components"] == []
    assert second["preset_components"] == []
    assert registry.seen == ["slipping", None]


async def test_retrying_a_preset_turn_answers_from_normal_routing():
    graph = _graph()
    composer = _composer()
    preset = _config(
        screen_context={"screen": "world", "compose": "slipping"}, composer=composer
    )
    await graph.ainvoke(_input(), preset)

    retry = _config(composer=composer)  # the retry path carries no screen_context
    retry["configurable"]["retry_mode"] = True
    await graph.ainvoke(_input(), retry)

    values = (await graph.aget_state(retry)).values
    assert values["components"] == []
    assert values["envelope"].routing_method == "embedding"
    assert composer.compose_slipping.await_count == 1


def test_make_graph_input_resets_the_per_turn_preset_components():
    assert _input()["preset_components"] == []
