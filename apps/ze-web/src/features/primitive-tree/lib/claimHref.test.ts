import { describe, expect, it } from "vitest";
import { claimHref } from "./claimHref";

describe("claimHref", () => {
  it("opens goals and workflows on their pages", () => {
    expect(claimHref("goal", "g-1")).toBe("/doing/goals/g-1");
    expect(claimHref("workflow", "w-1")).toBe("/doing/workflows/w-1");
  });

  it("opens a loop on World", () => {
    expect(claimHref("loop", "l-1")).toBe("/");
  });

  it("has no page for subjects the web app does not show", () => {
    expect(claimHref("held_write", "h-1")).toBeNull();
    expect(claimHref("hypothesis", "x")).toBeNull();
    expect(claimHref("person", "x")).toBeNull();
  });
});
