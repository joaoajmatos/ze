import { describe, expect, it } from "vitest";
import { resolveScreenContext } from "./resolve-screen";

describe("resolveScreenContext", () => {
  it.each([
    ["/", "", { screen: "world" }],
    ["/world/priority", "", { screen: "world.priority" }],
    ["/ask", "", { screen: "ask" }],
    ["/ask/t-1", "", { screen: "ask" }],
    ["/doing", "", { screen: "doing" }],
    ["/doing/goals", "", { screen: "doing.goals" }],
    ["/doing/goals/g1", "", { screen: "doing.goals", goal_id: "g1" }],
    ["/doing/workflows", "", { screen: "doing.workflows" }],
    ["/doing/workflows/w1", "", { screen: "doing.workflows", workflow_id: "w1" }],
    ["/doing/workflows/w1", "?execution=e1", { screen: "doing.workflows", workflow_id: "w1", execution_id: "e1" }],
    ["/doing/skills", "", { screen: "doing.skills" }],
    ["/doing/procedures", "", { screen: "doing.procedures" }],
    ["/doing/workspace", "", { screen: "doing.workspace" }],
    ["/mind", "", { screen: "mind" }],
    ["/mind/graph", "", { screen: "mind.graph" }],
    ["/governance", "", { screen: "governance" }],
    ["/governance/data", "", { screen: "governance.data" }],
    ["/governance/settings", "", { screen: "governance.settings" }],
  ])("%s%s", (pathname, search, expected) => {
    expect(resolveScreenContext(pathname, search)).toEqual(expected);
  });

  it("names a plugin page by its path", () => {
    expect(resolveScreenContext("/contacts", "")).toEqual({ screen: "contacts" });
  });

  it("ignores an execution param outside a workflow", () => {
    expect(resolveScreenContext("/doing/goals/g1", "?execution=e1")).toEqual({ screen: "doing.goals", goal_id: "g1" });
  });
});
