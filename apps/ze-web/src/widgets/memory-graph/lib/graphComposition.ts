import type { GraphEdge, GraphEntityNode } from "@myguyze/ze-client";
import type { ChartPoint } from "@myguyze/ze-ui/charts";

const RELATION_SLICE_CAP = 6;

function countsToPoints(counts: Map<string, number>): ChartPoint[] {
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([x, y]) => ({ x, y }));
}

function capSlices(points: ChartPoint[], cap: number): ChartPoint[] {
  if (points.length <= cap) return points;
  const head = points.slice(0, cap - 1);
  const rest = points.slice(cap - 1).reduce((sum, point) => sum + point.y, 0);
  return [...head, { x: "Other", y: rest }];
}

export function graphComposition(
  nodes: GraphEntityNode[],
  edges: GraphEdge[],
): { byEntityType: ChartPoint[]; byRelationType: ChartPoint[] } {
  const entityCounts = new Map<string, number>();
  for (const node of nodes) {
    entityCounts.set(node.entity_type, (entityCounts.get(node.entity_type) ?? 0) + 1);
  }
  const relationCounts = new Map<string, number>();
  for (const edge of edges) {
    relationCounts.set(edge.predicate, (relationCounts.get(edge.predicate) ?? 0) + 1);
  }
  return {
    byEntityType: countsToPoints(entityCounts),
    byRelationType: capSlices(countsToPoints(relationCounts), RELATION_SLICE_CAP),
  };
}
