import { describe, expect, it } from "vitest";
import { levelFromSamples } from "./level";

describe("levelFromSamples", () => {
  it("is 0 for silence", () => {
    expect(levelFromSamples(new Float32Array(64))).toBe(0);
  });
  it("is 1 for a full-scale square wave", () => {
    expect(levelFromSamples(new Float32Array(64).map((_, i) => (i % 2 ? 1 : -1)))).toBe(1);
  });
  it("maps an RMS of 0.01 (-40 dBFS) to 0.4", () => {
    expect(levelFromSamples(new Float32Array(64).fill(0.01))).toBeCloseTo(0.4, 5);
  });
  it("clamps to 0..1", () => {
    expect(levelFromSamples(new Float32Array(64).fill(4))).toBe(1);
    expect(levelFromSamples(new Float32Array(64).fill(0.0001))).toBe(0);
  });
  it("is 0 for no samples", () => {
    expect(levelFromSamples(new Float32Array(0))).toBe(0);
  });
});
