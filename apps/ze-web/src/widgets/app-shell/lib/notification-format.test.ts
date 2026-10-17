import { describe, expect, it } from "vitest";
import { notificationHref } from "./notification-format";

const n = (target_type: string | null, target_id: string | null, target_parent_id?: string | null) => ({
  target_type,
  target_id,
  target_parent_id,
});

describe("notificationHref", () => {
  it.each([
    ["open_loop", "l-1", undefined, "/"],
    ["hypothesis", "h-1", undefined, "/"],
    ["goal", "g-1", undefined, "/doing/goals/g-1"],
    ["goal_gate", "gate-1", "g-1", "/doing/goals/g-1"],
    ["goal_suggestion", "s-1", undefined, "/doing"],
    ["workflow_execution", "e-1", "w-1", "/doing/workflows/w-1?execution=e-1"],
      ["held_write", "r-1", undefined, "/"],
    ["workspace_run", "run-1", undefined, "/doing/workspace"],
    ["chat_thread", "t-1", undefined, "/ask/t-1"],
    ["reminder", "rem-1", undefined, "/"],
    ["person", "c-1", undefined, "/mind"],
    ["insight", "i-1", undefined, "/mind"],
  ])("%s -> %s", (type, id, parent, href) => {
    expect(notificationHref(n(type, id, parent))).toBe(href);
  });

  it("falls back to the list when a parent id is missing", () => {
    expect(notificationHref(n("goal_gate", "gate-1"))).toBe("/doing/goals");
    expect(notificationHref(n("workflow_execution", "e-1", null))).toBe("/doing/workflows");
  });

  it("returns null for an unknown type or a missing target", () => {
    expect(notificationHref(n("martian", "x"))).toBeNull();
    expect(notificationHref(n(null, "x"))).toBeNull();
    expect(notificationHref(n("goal", null))).toBeNull();
  });
});
