import { describe, expect, it } from "vitest";
import { beliefSentence, sinceLabel, sourceWords } from "./belief";

describe("beliefSentence", () => {
  it("keeps a sentence value as is", () => {
    expect(beliefSentence("food_preference", "prefers aisle seats")).toBe("prefers aisle seats");
  });

  it("does not take a multi-word proper noun for a sentence", () => {
    expect(beliefSentence("works_at", "Acme Corp Ltd")).toBe("Works at Acme Corp Ltd");
    expect(beliefSentence("lives_in", "New York City")).toBe("Lives in New York City");
  });

  it("joins the humanised predicate and a short value", () => {
    expect(beliefSentence("works_at", "Acme")).toBe("Works at Acme");
    expect(beliefSentence("exercise_habit", "runs")).toBe("Exercise habit runs");
  });

  it("falls back for an empty value", () => {
    expect(beliefSentence("works_at", "")).toBe("A fact Ze holds");
    expect(beliefSentence("works_at", null)).toBe("A fact Ze holds");
    expect(beliefSentence(null, "  ")).toBe("A fact Ze holds");
  });

  it("never prints an underscore key", () => {
    for (const [k, v] of [["a_b_c", "x"], ["a_b", "Foo Bar Baz"], ["a_b", "does a thing"]] as const) {
      expect(beliefSentence(k, v)).not.toMatch(/_/);
    }
  });
});

describe("sinceLabel", () => {
  const now = new Date("2026-10-17T12:00:00Z");
  it("speaks in days then dates", () => {
    expect(sinceLabel("2026-10-17T08:00:00Z", now)).toBe("since today");
    expect(sinceLabel("2026-10-16T08:00:00Z", now)).toBe("since yesterday");
    expect(sinceLabel("2026-10-14T08:00:00Z", now)).toBe("since 3 days ago");
    expect(sinceLabel("2026-08-01T08:00:00Z", now)).toBe("since 1 Aug");
  });
});

describe("sourceWords", () => {
  it("names provenance and agent in words", () => {
    expect(sourceWords("prompt_supplied", "companion")).toBe("from what you gave me, via companion");
    expect(sourceWords("synthesized", "dream_memory")).toBe("I worked it out, via dream memory");
    expect(sourceWords(null, "messenger")).toBe("via messenger");
    expect(sourceWords("live_search", null)).toBe("from a web search");
  });
});
