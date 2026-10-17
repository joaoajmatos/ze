import { describe, expect, it } from "vitest";
import { concernChip, concernGlyph, concernPosture, concernStateWords, provenanceWords, type Concern } from "./concern";

const c = (extra: Partial<Concern>): Pick<Concern, "kind" | "state" | "claimKind" | "provenance" | "confirmed" | "partial" | "slipped"> => ({
  kind: "loop", state: "active", claimKind: "fact", provenance: "email", confirmed: false, partial: false, slipped: false, ...extra,
});

describe("concernPosture", () => {
  it.each([
    ["told loop", c({ provenance: "user_declared" }), "told"],
    ["evidenced loop", c({}), "evidenced"],
    ["drifting stays evidenced", c({ state: "drifting" }), "evidenced"],
    ["inferred loop", c({ claimKind: "inference" }), "inferred"],
    ["suspected loop by state", c({ state: "suspected" }), "suspected"],
    ["user-declared but suspected stays suspected", c({ state: "suspected", provenance: "user_declared" }), "suspected"],
    ["inference hypothesis", c({ kind: "hypothesis", claimKind: "inference", provenance: null, state: "open" }), "inferred"],
    ["suspicion hypothesis", c({ kind: "hypothesis", claimKind: "suspicion", provenance: null, state: "open" }), "suspected"],
    ["confirmed hypothesis is evidenced, not told", c({ kind: "hypothesis", claimKind: "inference", confirmed: true, state: "confirmed" }), "evidenced"],
    ["goal", c({ kind: "goal", claimKind: null, provenance: null }), "goal"],
    ["relationship is no claim", c({ kind: "relationship", claimKind: null, provenance: null, state: null }), "plain"],
    ["reminder is no claim", c({ kind: "reminder", claimKind: null, provenance: null, state: "upcoming" }), "plain"],
    ["partial record claims nothing", c({ partial: true, claimKind: null, state: null, provenance: null }), "plain"],
  ])("%s", (_n, input, want) => {
    expect(concernPosture(input)).toBe(want);
  });
});

describe("glyph, chip and words", () => {
  it("plain has no glyph and no chip; the rest do", () => {
    expect(concernGlyph("plain")).toBeNull();
    expect(concernChip("plain")).toBeNull();
    expect(concernGlyph("evidenced")).toBe("told");
    expect(concernGlyph("inferred")).toBe("inferred");
    expect(concernGlyph("goal")).toBe("goal");
    expect(concernChip("suspected")).toBe("suspected");
  });
  it("no state or provenance word is a raw enum", () => {
    expect(concernStateWords({ kind: "goal", state: "awaiting_gate", slipped: false })).toBe("waiting on you");
    expect(concernStateWords({ kind: "goal", state: "active", slipped: true })).toBe("stuck");
    expect(concernStateWords({ kind: "hypothesis", state: "confirmed", slipped: false })).toBe("confirmed by you");
    for (const p of ["user_declared", "graph_recall", "live_search", "prompt_supplied", "synthesized"]) expect(provenanceWords(p)).not.toMatch(/_/);
    expect(provenanceWords("email")).toBe("email");
  });
});
