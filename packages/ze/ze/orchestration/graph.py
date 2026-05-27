from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import END
from langgraph.graph import StateGraph

from ze.orchestration import edges
from ze.orchestration.nodes import confirmation, context, execution, memory, routing
from ze_core.orchestration.graph import graph_builder


def _wire_ze_nodes(builder: StateGraph) -> None:
    """Swap ze-core node runnables for Ze implementations (contacts, telemetry, …)."""
    replacements = {
        "embed_route": routing.embed_route,
        "decompose": routing.decompose,
        "fetch_context": context.fetch_context,
        "capability_check": execution.capability_check,
        "execute_tool": execution.execute_tool,
        "draft_response": execution.draft_response,
        "await_confirmation": confirmation.await_confirmation,
        "synthesize": memory.synthesize,
        "write_memory": memory.write_memory,
    }
    for name, fn in replacements.items():
        spec = builder.nodes[name]
        if hasattr(spec, "runnable"):
            spec.runnable = fn
        else:
            builder.nodes[name] = fn


def build_graph(checkpointer: AsyncPostgresSaver):
    """Ze conversation graph: ze-core skeleton + Ze nodes + plan_sequential."""
    builder = graph_builder()
    _wire_ze_nodes(builder)

    builder.add_node("plan_sequential", routing.plan_sequential)

    builder.add_conditional_edges(
        "embed_route",
        edges.after_embed_route,
        {
            "decompose": "decompose",
            "fetch_context": "fetch_context",
            "plan_sequential": "plan_sequential",
        },
    )
    builder.add_conditional_edges(
        "decompose",
        edges.after_decompose,
        {"plan_sequential": "plan_sequential", "fetch_context": "fetch_context"},
    )
    builder.add_edge("plan_sequential", END)

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["await_confirmation"],
    )
