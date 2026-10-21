import { describe, expect, it } from "vitest";
import { groupScriptRows, isDelegateLike, scriptSummary } from "./script-rows";

const row = (over: Record<string, unknown>) => ({ name: "get_goals", result_snippet: "", duration_ms: 10, success: true, access: "read", ...over }) as never;
const script = (over: Record<string, unknown> = {}) =>
  row({ name: "run_tool_script", call_id: "s1", access: "script", duration_ms: 420, script: { source: "x", source_cut: false, outcome: "ok", limit: null }, ...over });

describe("groupScriptRows", () => {
  it("nests rows by parent_call_id under their script row in order and keeps the rest top level", () => {
    const rows = [row({ name: "a", call_id: "c0" }), script(), row({ name: "b", call_id: "c2", parent_call_id: "s1" }), row({ name: "c", call_id: "c3", parent_call_id: "s1" }), row({ name: "d", call_id: "c4" })];
    const nodes = groupScriptRows(rows);
    expect(nodes.map((n) => n.call.name)).toEqual(["a", "run_tool_script", "d"]);
    expect(nodes[1].children.map((c) => c.name)).toEqual(["b", "c"]);
    expect(nodes[0].children).toEqual([]);
  });

  it("keeps an orphan top level", () => {
    const nodes = groupScriptRows([row({ name: "o", call_id: "c1", parent_call_id: "gone" })]);
    expect(nodes.map((n) => n.call.name)).toEqual(["o"]);
  });

  it("nests a child that arrives before its script row", () => {
    const nodes = groupScriptRows([row({ name: "b", call_id: "c2", parent_call_id: "s1" }), script()]);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].children.map((c) => c.name)).toEqual(["b"]);
  });
});

describe("scriptSummary", () => {
  it("reads outcome, call count and duration", () => {
    const [node] = groupScriptRows([script(), ...["a", "b", "c"].map((n, i) => row({ name: n, call_id: `k${i}`, parent_call_id: "s1" }))]);
    expect(scriptSummary(node)).toBe("Script · ok · 3 calls · 420 ms");
  });

  it("names the limit that stopped it and singular call", () => {
    const [node] = groupScriptRows([script({ script: { source: "x", source_cut: false, outcome: "limit", limit: "spend" }, duration_ms: 90 }), row({ call_id: "k", parent_call_id: "s1" })]);
    expect(scriptSummary(node)).toBe("Script · limit: spend · 1 call · 90 ms");
  });
});

describe("isDelegateLike", () => {
  it("styles script like delegate", () => {
    expect(isDelegateLike("script")).toBe(true);
    expect(isDelegateLike("delegate")).toBe(true);
    expect(isDelegateLike("read")).toBe(false);
  });
});
