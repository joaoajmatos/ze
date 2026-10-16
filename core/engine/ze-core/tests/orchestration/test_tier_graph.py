"""choose_tier inside the real graph: budget and write pauses, and retry (phase 182, T020).

The confirmation nodes are stubs paused with ``interrupt_before``; only the execution node
may import ``interrupt`` (the 181 guard in test_no_gate_names.py).
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from ze_agents.interface.types import RawInput
from ze_agents.registry import clear_registry
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext, AgentResult
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
        subtasks=[SubTask(agent="t182", prompt="thanks", model="full-m")],
        requires_synthesis=False,
    )
    return {"envelope": envelope}


async def _fetch_context(state, config):
    ctx = AgentContext(
        session_id=state["session_id"],
        prompt=state["prompt"],
        messages=[{"role": "user", "content": state["prompt"]}],
    )
    return {"agent_context": ctx, "memory_context": None}


async def _noop(state, config):
    return {}


def _graph(models_used: list[str], *, budget_pause=False, write_pause=False):
    state = {"parked": False}

    async def preflight(state_, config):
        if budget_pause:
            return {"budget_status": {"over": True}, "budget_approved": False}
        return {}

    async def await_budget_confirmation(state_, config):
        return {"budget_approved": True}

    async def execute_tool(state_, config):
        models_used.append(state_["envelope"].subtasks[0].model)
        if write_pause and not state["parked"]:
            state["parked"] = True
            return {"write_confirmation": {"items": 1}, "parked_subtasks": [0]}
        return {
            "write_confirmation": None,
            "parked_subtasks": [],
            "agent_result": AgentResult(agent="t182", response="done"),
        }

    async def await_write_confirmation(state_, config):
        return {}

    overrides = {
        "preprocess": _noop,
        "embed_route": _embed_route,
        "decompose": _noop,
        "fetch_context": _fetch_context,
        "match_skills": _noop,
        "preflight": preflight,
        "await_budget_confirmation": await_budget_confirmation,
        "execute_tool": execute_tool,
        "await_write_confirmation": await_write_confirmation,
        "correlate": _noop,
        "surface_loops": _noop,
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
        interrupt_before=["await_budget_confirmation", "await_write_confirmation"],
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


def _input(text="thanks"):
    return make_graph_input(RawInput(text=text), "s1")


async def test_the_tier_is_decided_before_preflight_and_runs_the_light_model():
    judge, client = _judge(0.05)
    models: list[str] = []
    graph = _graph(models)
    config = _config(judge)

    await graph.ainvoke(_input(), config)

    assert len(client.calls) == 1
    assert models == ["light-m"]
    final = (await graph.aget_state(config)).values
    assert final["tier"].tier == "simple" and final["tier"].model == "light-m"


async def test_a_budget_pause_and_resume_judges_once_and_runs_the_decided_model():
    judge, client = _judge(0.05)
    models: list[str] = []
    graph = _graph(models, budget_pause=True)
    config = _config(judge)

    await graph.ainvoke(_input(), config)
    paused = await graph.aget_state(config)
    assert paused.next == ("await_budget_confirmation",)
    assert models == [] and len(client.calls) == 1

    await graph.ainvoke(None, config)

    assert len(client.calls) == 1
    assert models == ["light-m"]


async def test_a_write_confirmation_loop_judges_once_and_keeps_the_decided_model():
    judge, client = _judge(0.05)
    models: list[str] = []
    graph = _graph(models, write_pause=True)
    config = _config(judge)

    await graph.ainvoke(_input(), config)
    paused = await graph.aget_state(config)
    assert paused.next == ("await_write_confirmation",)
    assert models == ["light-m"]

    await graph.ainvoke(None, config)

    assert len(client.calls) == 1
    assert models == ["light-m", "light-m"]


async def test_a_retry_mode_turn_judges_again():
    judge, client = _judge(0.05)
    graph = _graph([])
    config = _config(judge, retry_mode=True)

    await graph.ainvoke(_input(), config)
    assert len(client.calls) == 1

    await graph.ainvoke(_input(), config)
    assert len(client.calls) == 2
    judgments = (await graph.aget_state(config)).values["judgments"]
    assert [j.question_id for j in judgments] == [Q_DEEP]


async def test_a_new_turn_does_not_inherit_the_previous_tier():
    judge, _ = _judge(0.05)
    models: list[str] = []
    graph = _graph(models)
    config = _config(judge)
    await graph.ainvoke(_input(), config)
    assert (await graph.aget_state(config)).values["tier"].tier == "simple"

    off = TierJudge(FakeSystemOneClient(), ComplexitySurfaceConfig(), {})
    config2 = _config(off)
    await graph.ainvoke(_input("again"), config2)
    assert (await graph.aget_state(config2)).values["tier"].decided_by == "off"
    assert models == ["light-m", "full-m"]
