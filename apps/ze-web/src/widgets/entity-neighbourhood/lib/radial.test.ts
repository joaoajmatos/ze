import type { GraphEdge, GraphEntityNode } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { MAX_NEIGHBOURS, radialLayout } from "./radial";

const node = (id: string, name: string): GraphEntityNode => ({ id, entity_type: "person", canonical_name: name, aliases: [], attrs: {}, degree: 1 });
const edge = (target: string, predicate: string): GraphEdge => ({ id: `e-${target}`, source_id: "c", target_id: target, predicate, confidence: 1 });

const centre = node("c", "Ada");

describe("radialLayout", () => {
  it("is deterministic for the same input", () => {
    const ns = [node("a", "Zed"), node("b", "Bob")];
    const es = [edge("a", "works_with"), edge("b", "works_with")];
    expect(radialLayout(centre, ns, es, 2)).toEqual(radialLayout(centre, [...ns].reverse(), [...es].reverse(), 2));
  });

  it("groups by predicate in a fixed order and sorts by name inside a group", () => {
    const ns = [node("a", "Zed"), node("b", "Bob"), node("c2", "Cleo")];
    const es = [edge("a", "works_with"), edge("b", "knows"), edge("c2", "knows")];
    const out = radialLayout(centre, ns, es, 3);
    expect(out.groups.map((g) => g.predicate)).toEqual(["knows", "works_with"]);
    expect(out.groups[0].nodes.map((n) => n.node.canonical_name)).toEqual(["Bob", "Cleo"]);
  });

  it("puts nodes on one ring around the centre", () => {
    const out = radialLayout(centre, [node("a", "A"), node("b", "B")], [edge("a", "knows"), edge("b", "knows")], 2);
    for (const n of out.groups.flatMap((g) => g.nodes)) {
      expect(Math.round(Math.hypot(n.x - out.centre.x, n.y - out.centre.y))).toBe(out.radius);
    }
  });

  it("caps at 20 and reports the rest from the total", () => {
    const ns = Array.from({ length: 24 }, (_, i) => node(`n${i}`, `N${String(i).padStart(2, "0")}`));
    const es = ns.map((n) => edge(n.id, "knows"));
    const out = radialLayout(centre, ns, es, 30);
    expect(out.shown).toBe(MAX_NEIGHBOURS);
    expect(out.more).toBe(10);
  });

  it("handles an empty neighbourhood", () => {
    const out = radialLayout(centre, [], [], 0);
    expect(out.groups).toEqual([]);
    expect(out.shown).toBe(0);
    expect(out.more).toBe(0);
  });

  it("files a neighbour without an edge under 'related'", () => {
    const out = radialLayout(centre, [node("a", "A")], [], 1);
    expect(out.groups[0].predicate).toBe("related");
  });
});
