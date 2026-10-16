"""choose_tier inside the real graph: confirmation resume and retry (phase 182, T020)."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from ze_agents.interface.types import RawInput
from ze_agents.registry import clear_registry
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext, AgentResult, GateDecision
from ze_core.checkpoint_serde import build_checkpoint_serde
from ze_core.conversation.turn import make_graph_input
from ze_core.orchestration.edges import after_decompose, after_embed_route
from ze_core.orchestration.graph import graph_builder
from ze_core.routing.tier import Q_DEEP, ComplexitySurfaceConfig, TierJudge
from ze_core.routing.types import RoutingEnvelope, SubTask
from tests.support.routing import FakeSystemOneClient, register_agent


@pytest.fixture(autouse=True)
def registry():
    clear_registry()
    register_agent("t182", model="full-m", model_simple="light-m")
    yield
    clear_registry()


async def _embed_route(state, config):
    envelope = RoutingEnvelope(
        primary_agent="t182",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[
            SubTask(agent="t182", intent="read", prompt="thanks", model="full-m")
        ],
        requires_synthesis=False,
    )
    return {"envelope": envelope}


async def _fetch_context(state, config):
    ctx = AgentContext(
        session_id=state["session_id"],
        prompt=state["prompt"],
        intent="read",
        messages=[{"role": "user", "content": state["prompt"]}],
    )
    return {"agent_context": ctx, "memory_context": None}


async def _noop(state, config):
    return {}


async def _capability_check(state, config):
    return {"gate_decision": GateDecision.DRAFT}


def _graph(models_used: list[str]):
    async def execute_tool(state, config):
        models_used.append(state["envelope"].subtasks[0].model)
        return {"agent_result": AgentResult(agent="t182", response="done")}

    overrides = {
        "preprocess": _noop,
        "embed_route": _embed_route,
        "decompose": _noop,
        "fetch_context": _fetch_context,
        "match_skills": _noop,
        "capability_check": _capability_check,
        "execute_tool": execute_tool,
        "await_subtask_confirmation": _noop,
        "correlate": _noop,
        "surface_loops": _noop,
        "draft_response": _noop,
        "await_confirmation": _noop,
        "synthesize": _noop,
        "record_trace": _noop,
        "write_memory": _noop,
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
        interrupt_before=["await_confirmation"],
    )


def _judge(noul: float):
    answer = SystemOneAnswer(type="noul", noul=noul)
    client = FakeSystemOneClient(
        SystemOneResult(outcome="ok", model="jev", answers={Q_DEEP: answer})
    )
    judge = TierJudge(client, ComplexitySurfaceConfig(enabled=True, simple_max=0.2), {})
    return judge, client


def _config(judge, thread_id="t1", **extra) -> dict:
    return {"configurable": {"thread_id": thread_id, "tier_judge": judge, **extra}}


async def test_confirmation_resume_judges_once_and_runs_the_decided_model():
    judge, client = _judge(0.05)
    models: list[str] = []
    graph = _graph(models)
    config = _config(judge)

    await graph.ainvoke(make_graph_input(RawInput(text="thanks"), "s1"), config)
    paused = await graph.aget_state(config)
    assert paused.next == ("await_confirmation",)
    assert models == []
    assert len(client.calls) == 1

    await graph.ainvoke(None, config)

    assert len(client.calls) == 1
    assert models == ["light-m"]
    final = (await graph.aget_state(config)).values
    assert final["tier"].tier == "simple"
    assert final["tier"].model == "light-m"


async def test_a_retry_mode_turn_judges_again():
    judge, client = _judge(0.05)
    graph = _graph([])
    config = _config(judge, retry_mode=True)

    await graph.ainvoke(make_graph_input(RawInput(text="thanks"), "s1"), config)
    await graph.ainvoke(None, config)
    assert len(client.calls) == 1

    await graph.ainvoke(make_graph_input(RawInput(text="thanks"), "s1"), config)
    assert len(client.calls) == 2
    judgments = (await graph.aget_state(config)).values["judgments"]
    assert [j.question_id for j in judgments] == [Q_DEEP]


async def test_a_new_turn_does_not_inherit_the_previous_tier():
    judge, _ = _judge(0.05)
    models: list[str] = []
    graph = _graph(models)
    config = _config(judge)
    await graph.ainvoke(make_graph_input(RawInput(text="thanks"), "s1"), config)
    await graph.ainvoke(None, config)
    assert (await graph.aget_state(config)).values["tier"].tier == "simple"

    off = TierJudge(FakeSystemOneClient(), ComplexitySurfaceConfig(), {})
    config2 = _config(off)
    await graph.ainvoke(make_graph_input(RawInput(text="again"), "s1"), config2)
    await graph.ainvoke(None, config2)
    assert (await graph.aget_state(config2)).values["tier"].decided_by == "off"
    assert models == ["light-m", "full-m"]
