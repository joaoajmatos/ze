from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from ze_api.wiring.workflow_graph import build_workflow_graph


def _wrapped(node) -> bool:
    func = getattr(node.bound, "afunc", None) or getattr(node.bound, "func", None)
    return getattr(func, "__qualname__", "").startswith("timed.")


def test_every_workflow_graph_node_is_timed():
    graph = build_workflow_graph(MemorySaver())
    nodes = {n: node for n, node in graph.nodes.items() if not n.startswith("__")}
    assert "load_workflow_step" in nodes and "write_memory" in nodes
    assert [n for n, node in nodes.items() if not _wrapped(node)] == []
