import { describe, expect, it } from "vitest";
import { smoothLevel } from "./level";

describe("smoothLevel", () => {
  it("attacks at 0.5 per frame", () => {
    expect(smoothLevel(0, 1)).toBe(0.5);
  });

  it("releases at 0.12 per frame", () => {
    expect(smoothLevel(1, 0)).toBeCloseTo(0.88, 10);
  });

  it("stays in 0..1", () => {
    expect(smoothLevel(0.5, 5)).toBeLessThanOrEqual(1);
    expect(smoothLevel(0.5, -5)).toBeGreaterThanOrEqual(0);
    expect(smoothLevel(0, 0)).toBe(0);
  });
});
