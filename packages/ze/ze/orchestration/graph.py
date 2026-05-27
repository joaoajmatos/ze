from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import END

from ze.orchestration import edges
from ze.orchestration.nodes import context, execution, memory, routing
from ze_core.orchestration.graph import graph_builder


def build_graph(checkpointer: AsyncPostgresSaver):
    """Ze conversation graph: ze-core skeleton + Ze node overrides + plan_sequential."""
    builder = graph_builder(node_overrides={
        "fetch_context":  context.fetch_context,
        "execute_tool":   execution.execute_tool,
        "draft_response": execution.draft_response,
        "write_memory":   memory.write_memory,
        "decompose":      routing.decompose,
    })

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
