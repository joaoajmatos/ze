import type { FactDigestItem, MemoryFeedItem } from "@myguyze/ze-client";

/** An entity's fact as a feed item, so the same belief row shows it. */
export function factAsFeedItem(fact: FactDigestItem): MemoryFeedItem {
  return {
    id: fact.id,
    type: "fact",
    key: fact.key,
    value: fact.value,
    confidence: fact.confidence ?? null,
    reviewed: fact.reviewed ?? null,
    contradicted: fact.contradicted ?? null,
    provenance: fact.provenance ?? null,
    claim_kind: fact.claim_kind ?? null,
    summary: null,
    prompt_snippet: null,
    agent: fact.agent,
    created_at: fact.created_at ?? "",
  };
}
