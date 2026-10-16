"""A workflow run is never cut short by the graph's step limit (Phase 181, e2e finding 6).

Each workflow step passes through about a dozen graph nodes (a 2-step run takes
26 graph steps). A run started from a chat turn inherited LangChain's default
recursion_limit of 25 from the turn's runnable context and stopped with
"Recursion limit of 25 reached".
"""

from __future__ import annotations

from ze_automation.workflow.types import WorkflowStep

from tests.test_workflow_hold import Harness, registry  # noqa: F401


def _steps(n: int) -> list[WorkflowStep]:
    return [WorkflowStep(task=f"step {i}", id=f"s{i}") for i in range(n)]


async def test_a_five_step_workflow_runs_to_the_end() -> None:
    h = Harness([(f"done {i}", None) for i in range(5)])

    execution_id = await h.run(_steps(5))

    state = await h.graph.aget_state({"configurable": {"thread_id": str(execution_id)}})
    assert state.next == ()
    assert len(state.values["workflow_step_results"]) == 5


async def test_a_run_started_inside_a_chat_turn_is_not_capped_at_25_steps() -> None:
    """trigger_workflow runs inside the chat graph's execute_tool node; the
    workflow graph inherited that runnable context's recursion_limit of 25."""
    from langchain_core.runnables.config import var_child_runnable_config

    h = Harness([("done 0", None), ("done 1", None)])
    token = var_child_runnable_config.set({"recursion_limit": 25})
    try:
        execution_id = await h.run(_steps(2))
    finally:
        var_child_runnable_config.reset(token)

    state = await h.graph.aget_state({"configurable": {"thread_id": str(execution_id)}})
    assert state.next == ()
    assert len(state.values["workflow_step_results"]) == 2
