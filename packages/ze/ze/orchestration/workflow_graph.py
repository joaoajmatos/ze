from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import END

from ze.orchestration import edges
from ze.orchestration.graph import _wire_ze_nodes
from ze.orchestration.nodes import workflow
from ze_core.orchestration.graph import graph_builder


def build_workflow_graph(checkpointer: AsyncPostgresSaver):
    """Workflow execution graph — reuses Ze node implementations from graph_builder."""
    builder = graph_builder()
    _wire_ze_nodes(builder)

    # Workflow-specific nodes
    builder.add_node("load_workflow_step", workflow.load_workflow_step)
    builder.add_node("verify_step", workflow.verify_step)
    builder.add_node("workflow_synthesize", workflow.workflow_synthesize)
    builder.add_node("workflow_failed", workflow.workflow_failed)

    builder.set_entry_point("load_workflow_step")

    builder.add_edge("load_workflow_step", "embed_route")
    builder.add_edge("embed_route", "fetch_context")
    builder.add_edge("fetch_context", "capability_check")
    builder.add_conditional_edges(
        "capability_check",
        edges.after_capability_check_workflow,
        {"execute_tool": "execute_tool", "workflow_failed": "workflow_failed"},
    )
    builder.add_edge("execute_tool", "write_memory")
    builder.add_edge("write_memory", "verify_step")
    builder.add_conditional_edges(
        "verify_step",
        edges.after_verify_step,
        {
            "load_workflow_step": "load_workflow_step",
            "workflow_synthesize": "workflow_synthesize",
            "workflow_failed": "workflow_failed",
        },
    )
    builder.add_edge("workflow_synthesize", END)
    builder.add_edge("workflow_failed", END)

    return builder.compile(checkpointer=checkpointer)
