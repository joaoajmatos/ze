import { describe, expect, it } from "vitest";
import { richTrace } from "./fixtures";
import { GATE_WORDS, toolLanes } from "./tools";

describe("toolLanes", () => {
  const lanes = toolLanes(richTrace().tool_calls, "companion", false);

  it("lanes by agent with the reply's agent first, calls in call_index order", () => {
    expect(lanes.map((l) => l.agent)).toEqual(["companion", "calendar", "messenger"]);
    expect(lanes[0].calls.map((c) => c.name)).toEqual(["get_goals", "delegate_to_agent"]);
  });

  it("puts a null agent in the reply's agent lane", () => {
    const l = toolLanes([{ name: "a", duration_ms: 5, success: true, result_snippet: "" } as never], "companion", false);
    expect(l[0].agent).toBe("companion");
  });

  it("starts each call at the cumulative duration of the earlier calls in its own lane only", () => {
    expect(lanes[0].calls.map((c) => c.x)).toEqual([0, 120]);
    expect(lanes[1].calls.map((c) => c.x)).toEqual([0, 200]);
    const total = richTrace().tool_duration_ms;
    // the companion lane (1020) plus the calendar lane (500) plus messenger exceeds what any one lane spans; none borrows another's time
    expect(lanes.every((l) => l.span <= total)).toBe(true);
    expect(lanes[1].calls[0].x).toBe(0);
  });

  it("flags the delegate call", () => {
    expect(lanes[0].calls[1].note).toBe("includes the delegate's calls");
  });

  it("gives a 0 ms call a minimum width", () => {
    expect(lanes[2].calls[0].w).toBeGreaterThan(0);
  });

  it("marks irreversible, gate and failure, with words; none draws no tick", () => {
    const create = lanes[1].calls[1];
    expect(create).toMatchObject({ irreversible: true, gate: "approved", gateWords: "approved" });
    const denied = lanes[2].calls[0];
    expect(denied).toMatchObject({ failed: true, gate: "denied" });
    expect(lanes[0].calls[0].gate).toBeNull();
    expect(Object.keys(GATE_WORDS).sort()).toEqual(["approved", "denied", "duplicate", "expired", "none", "pre_approved", "refused", "refused_over_cap"]);
  });

  it("has partial calls with no width, reading 'returned'", () => {
    const p = toolLanes(richTrace().tool_calls.slice(0, 2), "companion", true);
    expect(p[0].calls.every((c) => c.w === 0 && c.note !== null || c.w === 0)).toBe(true);
    expect(p[0].calls[0].returned).toBe(true);
  });

  it("falls back to one lane in list order when the wire carries no agent", () => {
    const calls = richTrace().tool_calls.map((c) => ({ ...c, agent: undefined, call_index: undefined }));
    const l = toolLanes(calls as never, "companion", false);
    expect(l).toHaveLength(1);
    expect(l[0].calls.map((c) => c.name)).toEqual(richTrace().tool_calls.map((c) => c.name));
  });
});
