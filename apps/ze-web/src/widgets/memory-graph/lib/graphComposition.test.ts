import type { GraphEdge, GraphEntityNode } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { graphComposition } from "./graphComposition";

function node(entity_type: string, id: string): GraphEntityNode {
  return {
    id,
    entity_type,
    canonical_name: id,
    aliases: [],
    attrs: {},
    degree: 1,
  };
}

function edge(predicate: string, id: string): GraphEdge {
  return {
    id,
    source_id: "a",
    target_id: "b",
    predicate,
    confidence: 1,
  };
}

describe("graphComposition", () => {
  it("folds extra relation types into Other", () => {
    const edges = [
      "knows",
      "works_at",
      "lives_in",
      "likes",
      "follows",
      "mentions",
      "related_to",
    ].map((predicate, i) => edge(predicate, String(i)));

    const { byRelationType } = graphComposition([node("person", "p1")], edges);

    expect(byRelationType).toHaveLength(6);
    expect(byRelationType.at(-1)).toEqual({ x: "Other", y: 2 });
  });
});
