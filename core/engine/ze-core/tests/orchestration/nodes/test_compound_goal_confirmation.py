"""Goal writes confirm at the graph in a compound turn (phase 171 follow-up).

A tool-level interrupt from a child task of asyncio.gather would replay every
non-completed sibling on resume. The goals write intents stay CONFIRM, so the
per-subtask gate asks first, and the sibling write runs exactly once.
"""

import pytest

from ze_agents.interrupt import tool_interrupt_fn, workspace_confirmed
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.types import AgentContext, AgentResult, GateDecision, Intent, Mode
from ze_automation.agents.goals.agent import GoalAgent
from ze_core.capability import CapabilityGate
from ze_core.orchestration.nodes.execution import capability_check, execute_tool
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_memory.types import MemoryContext


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _register(name: str, intents: dict, runs: list):
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            runs.append(
                (
                    name,
                    ctx.intent,
                    workspace_confirmed.get(),
                    tool_interrupt_fn.get() is not None,
                )
            )
            return AgentResult(agent=name, response=name)

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = name
    _A.enabled = True
    _A.timeout = 30
    _A.intents = intents
    agent(_A)
    register_instance(name, _A())


def _state(runs):
    subtasks = [
        SubTask(agent="messenger", intent="create", prompt="email Ana"),
        SubTask(agent="goals", intent="create", prompt="create a goal"),
    ]
    envelope = RoutingEnvelope(
        primary_agent="messenger",
        confidence=0.9,
        score_gap=0.3,
        routing_method="haiku",
        is_compound=True,
        subtasks=subtasks,
        requires_synthesis=True,
    )
    return {
        "envelope": envelope,
        "agent_context": AgentContext(
            session_id="s1",
            prompt="email Ana and create a goal",
            intent="create",
            memory=MemoryContext(),
            messages=[],
        ),
        "session_overrides": {},
        "image_data": None,
    }


async def test_sibling_write_runs_once_across_pause_and_resume():
    runs: list = []
    _register("messenger", {"create": Intent(Mode.AUTONOMOUS)}, runs)
    _register("goals", GoalAgent.intents, runs)
    config = {"configurable": {"capability_gate": CapabilityGate(), "thread_id": "s1"}}

    state = _state(runs)
    state.update(await capability_check(state, config))
    decisions = {d["agent"]: d["decision"] for d in state["subtask_gate_decisions"]}
    assert decisions == {
        "messenger": GateDecision.EXECUTE,
        "goals": GateDecision.AWAIT_CONFIRMATION,
    }

    state.update(await execute_tool(state, config))
    assert [r[0] for r in runs] == ["messenger"]
    assert [p["agent"] for p in state["pending_subtask_awaits"]] == ["goals"]
    assert runs[0][3] is False  # no tool-level interrupt inside gather

    state["pending_subtask_awaits"] = []
    state["approved_subtask_indexes"] = [1]
    state.update(await execute_tool(state, config))

    assert [r[0] for r in runs] == ["messenger", "goals"]
    assert runs[1][2] is True  # the graph gate already got the user's yes
    assert runs[1][3] is False
    assert len(state["subtask_results"]) == 2


async def test_goals_read_subtask_does_not_pause_and_is_not_confirmed():
    runs: list = []
    _register("goals", GoalAgent.intents, runs)
    config = {"configurable": {"capability_gate": CapabilityGate(), "thread_id": "s1"}}
    state = _state(runs)
    state["envelope"] = RoutingEnvelope(
        primary_agent="goals",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=[
            SubTask(agent="goals", intent="read", prompt="what goals do I have?")
        ],
        requires_synthesis=False,
    )
    state.update(await capability_check(state, config))
    assert state["gate_decision"] == GateDecision.EXECUTE
    await execute_tool(state, config)
    assert runs == [("goals", "read", False, True)]


async def test_single_goal_write_approved_at_the_graph_is_not_asked_twice():
    runs: list = []
    _register("goals", GoalAgent.intents, runs)
    config = {"configurable": {"capability_gate": CapabilityGate(), "thread_id": "s1"}}
    state = _state(runs)
    state["envelope"] = RoutingEnvelope(
        primary_agent="goals",
        confidence=0.9,
        score_gap=0.3,
        routing_method="haiku",
        is_compound=False,
        subtasks=[SubTask(agent="goals", intent="create", prompt="create a goal")],
        requires_synthesis=False,
    )
    state["gate_decision"] = GateDecision.EXECUTE
    state["approved_agents"] = ["goals"]
    await execute_tool(state, config)
    assert runs == [("goals", "create", True, True)]
