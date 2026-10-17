import { describe, expect, it } from "vitest";
import { notificationHref } from "./notification-format";

const target = (target_type: string | null, target_id: string | null, target_parent_id?: string | null) => ({
  target_type,
  target_id,
  target_parent_id,
});

describe("notificationHref", () => {
  it("links a goal notification to its goal", () => {
    expect(notificationHref(target("goal", "g-1"))).toBe("/goals/g-1");
  });

  it("links a goal gate to the goal that owns it", () => {
    expect(notificationHref(target("goal_gate", "gate-1", "g-1"))).toBe("/goals/g-1");
  });

  it("links a workflow execution to its workflow with the execution selected", () => {
    expect(notificationHref(target("workflow_execution", "ex-1", "w-1"))).toBe(
      "/workflows/w-1?execution=ex-1",
    );
  });

  it("does not link a gate or execution that has no parent", () => {
    expect(notificationHref(target("goal_gate", "gate-1", null))).toBeNull();
    expect(notificationHref(target("workflow_execution", "ex-1"))).toBeNull();
  });

  it("no longer knows the workflow_run target type", () => {
    expect(notificationHref(target("workflow_run", "w-1"))).toBeNull();
  });

  it("does not link a goal suggestion: its id is not a goal id and the web app has no suggestion page", () => {
    expect(notificationHref(target("goal_suggestion", "s-1"))).toBeNull();
  });

  it("returns null without a target", () => {
    expect(notificationHref(target(null, "x"))).toBeNull();
    expect(notificationHref(target("goal", null))).toBeNull();
  });
});
