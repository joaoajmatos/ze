import type { GraphEdge, GraphEntityNode } from "@myguyze/ze-client";

export const MAX_NEIGHBOURS = 20;
const SIZE = 320;

export interface PlacedNode {
  node: GraphEntityNode;
  x: number;
  y: number;
}

export interface RadialGroup {
  predicate: string;
  nodes: PlacedNode[];
}

export interface RadialLayout {
  size: number;
  radius: number;
  centre: PlacedNode;
  groups: RadialGroup[];
  shown: number;
  more: number;
}

const round = (n: number) => Math.round(n * 100) / 100;

/** One ring around the centre, grouped by relation in alphabetical order, names sorted inside a group. */
export function radialLayout(
  centre: GraphEntityNode,
  neighbours: GraphEntityNode[],
  edges: GraphEdge[],
  total: number,
): RadialLayout {
  const predicateOf = new Map<string, string>();
  for (const e of [...edges].sort((a, b) => a.predicate.localeCompare(b.predicate))) {
    const other = e.source_id === centre.id ? e.target_id : e.source_id;
    if (!predicateOf.has(other)) predicateOf.set(other, e.predicate);
  }

  const capped = neighbours
    .slice(0, MAX_NEIGHBOURS)
    .sort((a, b) => a.canonical_name.localeCompare(b.canonical_name) || a.id.localeCompare(b.id));
  const byPredicate = new Map<string, GraphEntityNode[]>();
  for (const n of capped) {
    const p = predicateOf.get(n.id) ?? "related";
    byPredicate.set(p, [...(byPredicate.get(p) ?? []), n]);
  }

  const mid = SIZE / 2;
  const radius = SIZE / 2 - 48;
  const ordered = [...byPredicate.keys()].sort();
  const count = capped.length;
  let i = 0;
  const groups: RadialGroup[] = ordered.map((predicate) => ({
    predicate,
    nodes: byPredicate.get(predicate)!.map((node) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * i++) / Math.max(count, 1);
      return { node, x: round(mid + radius * Math.cos(angle)), y: round(mid + radius * Math.sin(angle)) };
    }),
  }));

  return {
    size: SIZE,
    radius,
    centre: { node: centre, x: mid, y: mid },
    groups,
    shown: count,
    more: Math.max(0, total - count),
  };
}
