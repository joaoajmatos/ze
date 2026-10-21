import { describe, it, expect } from "vitest";
import { queryKeys, refreshKeysForScreen } from "@/shared/lib/query-keys";

describe("refreshKeysForScreen", () => {
  it("returns query keys for core-owned screens", () => {
    expect(refreshKeysForScreen("goals")).toEqual([["goals"], ["priority-snapshot"], ["workflow-executions"]]);
    expect(refreshKeysForScreen("workflows")).toEqual([["workflows"]]);
    expect(refreshKeysForScreen("costs")).toEqual([["costs"]]);
  });

  it("resolves a module screen to the module's prefix key, covering every subject", () => {
    expect(refreshKeysForScreen("module:x.facet")).toEqual([["ui-module", "x.facet"]]);
    expect(queryKeys.uiModule("x.facet", "entity:e-1:")).toEqual(["ui-module", "x.facet", "entity:e-1:"]);
  });

  it("returns undefined for unknown screens and an empty module id", () => {
    expect(refreshKeysForScreen("chat")).toBeUndefined();
    expect(refreshKeysForScreen("news")).toBeUndefined();
    expect(refreshKeysForScreen("module:")).toBeUndefined();
    expect(refreshKeysForScreen("")).toBeUndefined();
  });

  it("has no plugin-page key", () => {
    expect("pluginPage" in queryKeys).toBe(false);
  });
});
