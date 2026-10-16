"""Compiles the workflow execution graph: the engine base graph plus ze-personal's workflow nodes.

Lives in the app because it joins ze_core and a plugin, which neither may import the other."""

from __future__ import annotations

from typing import Any


def begin_workflow_turn(workflow: Any) -> dict[str, Any]:
    """Set the telemetry flow and return the engine's base graph input for a workflow run."""
    from ze_agents.interface.types import RawInput
    from ze_core.conversation import make_graph_input
    from ze_core.telemetry.context import set_flow_context

    session_id = f"workflow:{workflow.id}"
    set_flow_context("workflow_execution", session_id=session_id)
    return make_graph_input(RawInput(text=f"[workflow] {workflow.name}"), session_id)


def build_workflow_graph(
    checkpointer: Any,
    plugins: list | None = None,
    node_overrides: dict[str, Any] | None = None,
) -> Any:
    """Build and compile the workflow execution graph."""
    from langgraph.constants import END

    from ze_core.orchestration.edges import after_embed_route
    from ze_core.orchestration.graph import graph_builder
    from ze_core.orchestration.state import build_state_type
    from ze_personal.graph.workflow import (
        after_preflight_workflow,
        after_handle_step_failure,
        after_route_branch,
        after_verify_step,
        handle_step_failure,
        load_workflow_step,
        retry_step,
        route_branch,
        verify_step,
        workflow_cancelled,
        workflow_failed,
        workflow_synthesize,
    )

    state_type = build_state_type(plugins or [])
    builder = graph_builder(state_type=state_type, node_overrides=node_overrides)

    builder.add_node("load_workflow_step", load_workflow_step)
    builder.add_node("verify_step", verify_step)
    builder.add_node("route_branch", route_branch)
    builder.add_node("handle_step_failure", handle_step_failure)
    builder.add_node("retry_step", retry_step)
    builder.add_node("workflow_synthesize", workflow_synthesize)
    builder.add_node("workflow_failed", workflow_failed)
    builder.add_node("workflow_cancelled", workflow_cancelled)

    builder.set_entry_point("load_workflow_step")

    builder.add_edge("load_workflow_step", "embed_route")
    builder.add_conditional_edges(
        "embed_route",
        after_embed_route,
        {"decompose": "decompose", "fetch_context": "fetch_context"},
    )
    builder.add_edge("decompose", "fetch_context")
    builder.add_conditional_edges(
        "preflight",
        after_preflight_workflow,
        {"execute_tool": "execute_tool", "workflow_failed": "workflow_failed"},
    )
    # Do NOT add execute_tool → write_memory here. The base graph already has
    # execute_tool → correlate (conditional). Adding a normal edge alongside it
    # creates a fan-out: both correlate AND write_memory fire after execute_tool,
    # causing verify_step to run twice per step — the early invocation sees the
    # next step index but no output, marking it as failed.
    builder.add_edge("write_memory", "verify_step")
    builder.add_conditional_edges(
        "verify_step",
        after_verify_step,
        {
            "route_branch": "route_branch",
            "handle_step_failure": "handle_step_failure",
            "retry_step": "retry_step",
        },
    )
    builder.add_edge("retry_step", "load_workflow_step")
    builder.add_conditional_edges(
        "handle_step_failure",
        after_handle_step_failure,
        {
            "load_workflow_step": "load_workflow_step",
            "workflow_synthesize": "workflow_synthesize",
            "workflow_failed": "workflow_failed",
            "workflow_cancelled": "workflow_cancelled",
        },
    )
    builder.add_conditional_edges(
        "route_branch",
        after_route_branch,
        {
            "load_workflow_step": "load_workflow_step",
            "workflow_synthesize": "workflow_synthesize",
            "workflow_failed": "workflow_failed",
            "workflow_cancelled": "workflow_cancelled",
        },
    )
    builder.add_edge("workflow_synthesize", END)
    builder.add_edge("workflow_failed", END)
    builder.add_edge("workflow_cancelled", END)

    for plugin in plugins or []:
        for name, fn in plugin.graph_nodes().items():
            builder.add_node(name, fn)
        plugin.graph_edges(builder)

    return builder.compile(checkpointer=checkpointer)
