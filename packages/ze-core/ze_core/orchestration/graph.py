from __future__ import annotations

from typing import Any


def graph_builder() -> Any:
    """Return a fully-wired but uncompiled StateGraph.

    All standard nodes and internal edges are added. The ``embed_route``
    conditional edge is intentionally omitted so callers can extend the
    graph (e.g. add a ``plan_sequential`` node) before wiring routing.

    Call ``add_conditional_edges("embed_route", ...)`` on the returned
    builder with your routing function and destination map, then compile:

        builder = graph_builder()
        # optionally add extra nodes here
        builder.add_conditional_edges(
            "embed_route",
            after_embed_route,
            {"decompose": "decompose", "fetch_context": "fetch_context"},
        )
        graph = builder.compile(checkpointer=checkpointer,
                                interrupt_before=["await_confirmation"])

    LangGraph imports are deferred so the rest of ze_core loads without
    langgraph present (useful in test environments).
    """
    from langgraph.constants import END
    from langgraph.graph import StateGraph

    from ze_core.orchestration import nodes
    from ze_core.orchestration.edges import after_capability_check, after_execute_tool
    from ze_core.orchestration.state import AgentState

    builder = StateGraph(AgentState)

    builder.add_node("embed_route",        nodes.embed_route)
    builder.add_node("decompose",          nodes.decompose)
    builder.add_node("fetch_context",      nodes.fetch_context)
    builder.add_node("capability_check",   nodes.capability_check)
    builder.add_node("execute_tool",       nodes.execute_tool)
    builder.add_node("draft_response",     nodes.draft_response)
    builder.add_node("await_confirmation", nodes.await_confirmation)
    builder.add_node("synthesize",         nodes.synthesize)
    builder.add_node("write_memory",       nodes.write_memory)

    builder.set_entry_point("embed_route")

    # embed_route and decompose routing conditionals are NOT wired here — see docstring.

    builder.add_edge("fetch_context",  "capability_check")
    builder.add_conditional_edges(
        "capability_check",
        after_capability_check,
        {"execute_tool": "execute_tool", "draft_response": "draft_response", "end_blocked": END},
    )
    builder.add_conditional_edges(
        "execute_tool",
        after_execute_tool,
        {"synthesize": "synthesize", "write_memory": "write_memory"},
    )
    builder.add_edge("draft_response",     "await_confirmation")
    builder.add_edge("await_confirmation", "execute_tool")
    builder.add_edge("synthesize",         "write_memory")
    builder.add_edge("write_memory",       END)

    return builder


def build_graph(checkpointer: Any) -> Any:
    """Build and compile the standard Ze Core graph with default routing.

    For applications that extend the graph (e.g. add custom nodes or alter the
    routing edge), call ``graph_builder()`` directly instead.
    """
    from ze_core.orchestration.edges import after_embed_route

    builder = graph_builder()
    builder.add_conditional_edges(
        "embed_route",
        after_embed_route,
        {"decompose": "decompose", "fetch_context": "fetch_context"},
    )
    builder.add_edge("decompose", "fetch_context")
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["await_confirmation"],
    )
