import { describe, expect, it } from "vitest";
import { chipLabelOf, glyphOf, postureOf, provenanceWords, stateWords, type PostureInput } from "./claim-posture";

const UNDERSCORED = (list: string[]) => list.filter((x) => x.includes("_"));
const RAW = [
  "awaiting_gate", "user_declared", "causal_guess", "graph_recall", "live_search", "prompt_supplied", "synthesized",
  "suspected", "active", "drifting", "closed", "dropped", "planning", "paused", "completed", "abandoned",
  "upcoming", "overdue", "fired", "open", "confirmed", "dismissed", "inference", "suspicion", "fact",
];

describe("postureOf", () => {
  const cases: [string, PostureInput, string][] = [
    ["told loop", { kind: "loop", state: "active", claimKind: "fact", provenance: "user_declared" }, "told"],
    ["evidenced loop", { kind: "loop", state: "active", claimKind: "fact", provenance: "email" }, "evidenced"],
    ["drifting loop stays evidenced", { kind: "loop", state: "drifting", claimKind: "fact", provenance: "email" }, "evidenced"],
    ["inferred loop", { kind: "loop", state: "active", claimKind: "inference", provenance: "conversation" }, "inferred"],
    ["suspected loop by state", { kind: "loop", state: "suspected", claimKind: "fact", provenance: "email" }, "suspected"],
    ["suspected loop by kind", { kind: "loop", state: "active", claimKind: "suspicion", provenance: "email" }, "suspected"],
    ["inference hypothesis", { kind: "hypothesis", claimKind: "inference" }, "inferred"],
    ["suspicion hypothesis", { kind: "hypothesis", claimKind: "suspicion" }, "suspected"],
    ["confirmed hypothesis is evidenced, not told", { kind: "hypothesis", claimKind: "inference", confirmed: true }, "evidenced"],
    ["partial record claims nothing", { kind: "loop", state: null, claimKind: null, provenance: null, partial: true }, "plain"],
    ["goal", { kind: "goal", state: "active" }, "goal"],
    ["relationship", { kind: "relationship" }, "plain"],
    ["reminder", { kind: "reminder", state: "upcoming" }, "plain"],
  ];
  it.each(cases)("%s", (_n, input, want) => {
    expect(postureOf(input)).toBe(want);
  });
});

describe("glyph and chip", () => {
  it("maps every posture to a glyph and a chip label", () => {
    expect(glyphOf("told")).toBe("told");
    expect(glyphOf("evidenced")).toBe("told");
    expect(glyphOf("inferred")).toBe("inferred");
    expect(glyphOf("suspected")).toBe("suspected");
    expect(glyphOf("goal")).toBe("goal");
    expect(glyphOf("plain")).toBeNull();
    expect(chipLabelOf("told")).toBe("you told me");
    expect(chipLabelOf("evidenced")).toBe("seen in evidence");
    expect(chipLabelOf("inferred")).toBe("asked, not stated");
    expect(chipLabelOf("suspected")).toBe("suspected");
    expect(chipLabelOf("goal")).toBe("goal");
    expect(chipLabelOf("plain")).toBeNull();
  });
});

describe("words never equal a raw enum", () => {
  it("state words", () => {
    const kinds = ["loop", "goal", "hypothesis", "relationship", "reminder"] as const;
    for (const kind of kinds) {
      for (const state of RAW) {
        const w = stateWords(kind, state);
        expect(UNDERSCORED(RAW), `${kind}/${state} -> ${w}`).not.toContain(w);
        expect(w).not.toMatch(/_/);
      }
    }
  });
  it("names the known states", () => {
    expect(stateWords("goal", "awaiting_gate")).toBe("waiting on you");
    expect(stateWords("loop", "drifting")).toBe("drifting");
    expect(stateWords("loop", "closed")).toBe("done");
    expect(stateWords("reminder", "overdue")).toBe("overdue");
    expect(stateWords("hypothesis", "confirmed")).toBe("confirmed by you");
  });
  it("provenance words", () => {
    for (const p of RAW) expect(provenanceWords(p)).not.toMatch(/_/);
    for (const p of ["user_declared", "graph_recall", "live_search", "prompt_supplied"]) expect(provenanceWords(p)).not.toBe(p);
    expect(provenanceWords("user_declared")).toBe("you told me");
    expect(provenanceWords("email")).toBe("email");
    expect(provenanceWords("graph_recall")).toBe("memory");
  });
});
