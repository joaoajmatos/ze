import { generatePath } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { askPath, goalPath, goalsPath, workflowsPath, placeOf, places, redirects, settingsDataPath, workflowPath } from "./places";

describe("places", () => {
  it("has the five places in order", () => {
    expect(places.map((p) => p.id)).toEqual(["world", "ask", "doing", "mind", "governance"]);
    expect(places.map((p) => p.path)).toEqual(["/", "/ask", "/doing", "/mind", "/governance"]);
    expect(places.map((p) => p.label)).toEqual(["World", "Ask", "Doing", "Mind", "Governance"]);
  });
});

describe("placeOf", () => {
  it.each([
    ["/", "world"],
    ["/world/priority", "world"],
    ["/ask", "ask"],
    ["/ask/t-1", "ask"],
    ["/doing", "doing"],
    ["/doing/goals", "doing"],
    ["/doing/goals/g-1", "doing"],
    ["/doing/workflows/w-1", "doing"],
    ["/doing/workspace", "doing"],
    ["/mind", "mind"],
    ["/mind/graph", "mind"],
    ["/governance", "governance"],
    ["/governance/data", "governance"],
    ["/governance/settings", "governance"],
  ])("%s is %s", (pathname, id) => {
    expect(placeOf(pathname)?.id).toBe(id);
  });

  it("returns null outside the five places", () => {
    expect(placeOf("/contacts")).toBeNull();
    expect(placeOf("/jarvis")).toBeNull();
    expect(redirects.some((r) => r.from.includes("jarvis") || r.to.includes("jarvis"))).toBe(false);
    expect(placeOf("/doingness")).toBeNull();
    expect(placeOf("/asking")).toBeNull();
  });
});

describe("redirects", () => {
  const resolve = (from: string, params: Record<string, string> = {}) => {
    const row = redirects.find((r) => r.from === from)!;
    return generatePath(row.to, params);
  };

  it.each([
    ["/loops", "/"],
    ["/priority", "/"],
    ["/reminders", "/"],
    ["/world", "/"],
    ["/goals", "/doing"],
    ["/workflows", "/doing"],
    ["/skills", "/doing"],
    ["/doing/goals", "/doing"],
    ["/doing/workflows", "/doing"],
    ["/doing/skills", "/doing"],
    ["/procedures", "/mind"],
    ["/doing/procedures", "/mind"],
    ["/contacts", "/mind"],
    ["/mind/graph", "/mind"],
    ["/workspace", "/governance"],
    ["/doing/workspace", "/governance"],
    ["/brain-memory", "/mind"],
    ["/brain-graph", "/mind"],
    ["/costs", "/governance"],
    ["/data", "/governance"],
    ["/governance/data", "/governance"],
    ["/settings", "/governance"],
    ["/governance/settings", "/governance"],
  ])("%s -> %s", (from, to) => {
    expect(resolve(from)).toBe(to);
  });

  it("carries params", () => {
    expect(resolve("/goals/:goalId", { goalId: "g-1" })).toBe("/doing/goals/g-1");
    expect(resolve("/workflows/:workflowId", { workflowId: "w-1" })).toBe("/doing/workflows/w-1");
  });

  it("names the module each old path lands on", () => {
    const hint = (from: string) => redirects.find((r) => r.from === from)?.hint;
    expect(hint("/goals")).toBe("goals");
    expect(hint("/doing/goals")).toBe("goals");
    expect(hint("/workflows")).toBe("workflows");
    expect(hint("/doing/workflows")).toBe("workflows");
    expect(hint("/skills")).toBe("skills");
    expect(hint("/doing/skills")).toBe("skills");
    expect(hint("/settings")).toBe("connections");
    expect(hint("/governance/settings")).toBe("connections");
    expect(hint("/data")).toBe("data");
    expect(hint("/governance/data")).toBe("data");
    expect(hint("/workspace")).toBe("files");
    expect(hint("/doing/workspace")).toBe("files");
    expect(hint("/costs")).toBeUndefined();
    expect(redirects.find((r) => r.from === "/settings")?.hintMap).toEqual({ "your-data": "data" });
  });

  it("covers every old core route once", () => {
    expect(new Set(redirects.map((r) => r.from)).size).toBe(redirects.length);
    expect(redirects).toHaveLength(25);
  });
});

describe("path helpers", () => {
  it("builds goal and workflow paths", () => {
    expect(goalsPath()).toBe("/doing#goals");
    expect(workflowsPath()).toBe("/doing#workflows");
    expect(goalPath("g-1")).toBe("/doing/goals/g-1");
    expect(workflowPath("w-1")).toBe("/doing/workflows/w-1");
    expect(workflowPath("w-1", "e-1")).toBe("/doing/workflows/w-1?execution=e-1");
  });

  it("builds ask paths", () => {
    expect(askPath()).toBe("/ask");
    expect(askPath("t-1")).toBe("/ask/t-1");
  });

  it("points the data section at Governance", () => {
    expect(settingsDataPath()).toBe("/governance#data");
  });
});
