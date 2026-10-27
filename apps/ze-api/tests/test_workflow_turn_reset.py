"""The workflow step reset is generated from the lifetime declarations (phase 200, US3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.tool import clear_tool_registry
from ze_agents.types import AgentContext, AgentResult
from ze_api.wiring.workflow_graph import begin_workflow_turn, build_workflow_graph
from ze_automation.workflow.types import WorkflowStep
from ze_core.orchestration.state import build_state_type
from ze_core.routing.types import RoutingEnvelope, SubTask

_RESET_KEYS = ("judgments", "components", "tier", "conductor_ledgers")


class _StatePlugin:
    def state_extensions(self):
        from ze_personal.graph.workflow import WorkflowAgentState

        return WorkflowAgentState

    def graph_nodes(self):
        return {}

    def graph_edges(self, builder):
        return None


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


class _Run:
    """A compiled workflow graph with stub nodes around the real workflow nodes."""

    def __init__(self, replies: list[str], cancel_after_calls: int | None = None):
        replies = list(replies)

        async def _run(this, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=this.name, response=replies.pop(0))

        cls = type(
            "_StepAgent",
            (BaseAgent,),
            {"name": "stepagent", "description": "d", "tools": [], "run": _run},
        )
        agent(cls)
        register_instance("stepagent", cls())

        self.seen: list[dict] = []
        self.store = AsyncMock()
        client = MagicMock()
        client.complete = AsyncMock(return_value="summary")
        self.scheduler = MagicMock()
        calls = {"n": 0}

        def _is_cancelled(execution_id) -> bool:
            calls["n"] += 1
            return cancel_after_calls is not None and calls["n"] > cancel_after_calls

        self.scheduler.is_cancelled = _is_cancelled
        self.configurable = {
            "openrouter_client": client,
            "workflow_store": self.store,
            "workflow_scheduler": self.scheduler,
        }
        self.plugins = [_StatePlugin()]
        self.graph = self._graph()

    def _graph(self):
        async def noop(state, config=None):
            return {}

        async def embed_route(state):
            self.seen.append({key: state.get(key) for key in _RESET_KEYS})
            envelope = RoutingEnvelope(
                primary_agent="stepagent",
                confidence=1.0,
                score_gap=1.0,
                routing_method="forced",
                is_compound=False,
                subtasks=[SubTask(agent="stepagent", prompt=state["prompt"])],
                requires_synthesis=False,
            )
            return {"envelope": envelope}

        async def fetch_context(state):
            return {
                "agent_context": AgentContext(
                    session_id=state["session_id"],
                    prompt=state["prompt"],
                    messages=[{"role": "user", "content": state["prompt"]}],
                )
            }

        async def write_memory(state, config=None):
            return {
                "judgments": ["step-judgment"],
                "components": [{"type": "card"}],
                "tier": "simple",
                "conductor_ledgers": [[{"agent": "stepagent", "status": "done"}]],
            }

        overrides = {
            "preprocess": noop,
            "embed_route": embed_route,
            "decompose": noop,
            "fetch_context": fetch_context,
            "match_skills": noop,
            "correlate": noop,
            "surface_loops": noop,
            "write_memory": write_memory,
        }
        return build_workflow_graph(
            MemorySaver(), plugins=self.plugins, node_overrides=overrides
        )

    def initial_state(self, steps: list[WorkflowStep]) -> dict:
        workflow = SimpleNamespace(id=uuid4(), name="Weekly summary")
        return {
            **begin_workflow_turn(workflow, state_type=build_state_type(self.plugins)),
            "workflow_id": workflow.id,
            "workflow_execution_id": uuid4(),
            "workflow_steps": steps,
            "current_step_id": steps[0].id,
            "workflow_step_results": [],
        }

    async def invoke(self, steps: list[WorkflowStep]) -> dict:
        config = {
            "configurable": {"thread_id": "workflow:t", **self.configurable},
            "recursion_limit": 60,
        }
        return await self.graph.ainvoke(self.initial_state(steps), config)


def _steps() -> list[WorkflowStep]:
    return [
        WorkflowStep(id="s1", task="first task"),
        WorkflowStep(id="s2", task="second task"),
    ]


async def test_step_two_starts_with_the_per_turn_state_reset():
    run = _Run(["one", "two"])
    out = await run.invoke(_steps())

    assert run.seen[0] == {
        "judgments": [],
        "components": [],
        "tier": None,
        "conductor_ledgers": [],
    }
    assert run.seen[1] == run.seen[0]
    assert [r.step_id for r in out["workflow_step_results"]] == ["s1", "s2"]


async def test_run_state_survives_the_step_reset():
    run = _Run(["one", "two"])
    out = await run.invoke(_steps())

    assert [s.id for s in out["workflow_steps"]] == ["s1", "s2"]
    assert out["visit_counts"] == {"s1": 1, "s2": 1}
    assert [r.output for r in out["workflow_step_results"]] == ["one", "two"]


async def test_a_cancel_still_reaches_workflow_cancelled_with_the_step_results():
    # load s1, load s2, then handle_step_failure sees the cancel.
    run = _Run(["one", ""], cancel_after_calls=2)
    out = await run.invoke(_steps())

    assert out["final_response"] == "Workflow run cancelled."
    assert out["current_step_id"] == "CANCELLED"
    run.store.finish_execution.assert_awaited_once()
    args, kwargs = run.store.finish_execution.await_args
    assert args[1] == "cancelled"
    assert "first task" in kwargs["summary"]
