import { Position, type Node, type Edge } from "@xyflow/react";
import dagre from "dagre";

const CHAR = 7.2;
const MIN_W = 150;
const MAX_W = 260;
const PAD_X = 44;
const LINE = 18;

/** A node is as wide as its label wants, up to a cap, and as tall as the lines that wrap. */
export function nodeSize(label: string): { width: number; height: number } {
  const width = Math.min(MAX_W, Math.max(MIN_W, Math.round(label.length * CHAR + PAD_X)));
  const lines = Math.min(3, Math.max(1, Math.ceil((label.length * CHAR) / (width - PAD_X))));
  return { width, height: 24 + lines * LINE };
}

export function layoutGraph<NodeData extends Record<string, unknown>>(
  nodes: Node<NodeData>[],
  edges: Edge[],
): Node<NodeData>[] {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 56 });

  for (const node of nodes) {
    graph.setNode(node.id, { width: node.width ?? MIN_W, height: node.height ?? 48 });
  }
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target);
  }

  dagre.layout(graph);

  return nodes.map((node) => {
    const { x, y } = graph.node(node.id);
    return {
      ...node,
      position: { x: x - (node.width ?? MIN_W) / 2, y: y - (node.height ?? 48) / 2 },
      targetPosition: Position.Top,
      sourcePosition: Position.Bottom,
    };
  });
}
