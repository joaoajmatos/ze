import { describe, expect, it } from "vitest";
import { chipLabelOf, glyphOf, postureOf, stateWords } from "./claim-posture";

const RAW = /_|^[a-z]+\.[a-z]+$/;

describe("claim posture table", () => {
  it.each([
    ["identity", "told", "", "told"],
    ["fact", "evidenced", "", "evidenced"],
    ["inference", "inferred", "inferred", "inferred"],
    ["suspicion", "suspected", "suspected", "suspected"],
  ] as const)("memory kind %s", (kind, posture, glyph, chip) => {
    expect(postureOf(kind)).toBe(posture);
    expect(glyphOf(posture)).toBe(glyph);
    expect(chipLabelOf(posture)).toBe(chip);
  });

  it("covers goals and plain claims", () => {
    expect(postureOf(null, "goal")).toBe("goal");
    expect(glyphOf("goal")).toBe("goal");
    expect(postureOf("priority")).toBe("plain");
    expect(postureOf("something_new")).toBe("plain");
    expect(postureOf(undefined)).toBe("plain");
    expect(chipLabelOf("plain")).toBe("noted");
  });

  it("derives posture from loop and hypothesis state when no claim kind is given", () => {
    expect(postureOf(null, "loop", "suspected")).toBe("suspected");
    expect(postureOf(null, "loop", "user_declared")).toBe("told");
    expect(postureOf(null, "hypothesis", "causal_guess")).toBe("inferred");
    expect(postureOf(null, "loop", "active")).toBe("evidenced");
  });

  it("never returns a raw enum as words", () => {
    for (const s of ["awaiting_gate", "user_declared", "causal_guess", "pattern", "tension", "convergence", "suspected", "active", "drifting", "closed", "dropped"]) {
      const words = stateWords(s);
      if (s.includes("_")) expect(words).not.toBe(s);
      expect(words).not.toMatch(RAW);
    }
    expect(stateWords("awaiting_gate")).toBe("waiting on you");
    expect(stateWords("user_declared")).toBe("you told me");
    expect(stateWords("unheard_of_state")).toBe("unheard of state");
  });
});
