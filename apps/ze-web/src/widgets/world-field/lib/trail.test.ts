import { describe, expect, it } from "vitest";
import { trailOf } from "./trail";

describe("trailOf", () => {
  it("has no trail without a prior (never invented)", () => {
    expect(trailOf(null, 0.6)).toBeNull();
    expect(trailOf(0.6, null)).toBeNull();
  });
  it("has no trail when confidence barely moved", () => {
    expect(trailOf(0.61, 0.6)).toBeNull();
  });
  it("runs from the prior to the current value", () => {
    expect(trailOf(0.8, 0.6)).toEqual({ from: 0.8, to: 0.6 });
    expect(trailOf(0.4, 0.7)).toEqual({ from: 0.4, to: 0.7 });
  });
});
