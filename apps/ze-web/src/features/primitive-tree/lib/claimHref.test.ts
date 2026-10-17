import { describe, expect, it } from "vitest";
import { claimHref } from "./claimHref";

describe("claimHref", () => {
  it("opens goals and workflows on their pages", () => {
    expect(claimHref("goal", "g-1")).toBe("/doing/goals/g-1");
    expect(claimHref("workflow", "w-1")).toBe("/doing/workflows/w-1");
  });

  it("opens loops, hypotheses and held writes on World with the item selected", () => {
    expect(claimHref("loop", "l-1")).toBe("/?focus=loop:l-1");
    expect(claimHref("hypothesis", "h-1")).toBe("/?focus=hypothesis:h-1");
    expect(claimHref("held_write", "h-1")).toBe("/?focus=held_write:h-1");
  });

  it("has no page for subjects the web app does not show", () => {
    expect(claimHref("person", "x")).toBeNull();
  });
});
