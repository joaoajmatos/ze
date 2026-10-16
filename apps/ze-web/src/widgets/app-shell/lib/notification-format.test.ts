import { describe, expect, it } from "vitest";
import { targetRoute } from "./notification-format";

describe("targetRoute", () => {
  it("links a goal notification to its goal", () => {
    expect(targetRoute("goal", "g-1")).toBe("/goals/g-1");
  });

  it("links a workflow run notification to its workflow", () => {
    expect(targetRoute("workflow_run", "w-1")).toBe("/workflows/w-1");
  });

  it("does not link a goal suggestion: its id is not a goal id and the web app has no suggestion page", () => {
    expect(targetRoute("goal_suggestion", "s-1")).toBeNull();
  });

  it("returns null without a target", () => {
    expect(targetRoute(null, "x")).toBeNull();
    expect(targetRoute("goal", null)).toBeNull();
  });
});
