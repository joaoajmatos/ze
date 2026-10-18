import { describe, expect, it } from "vitest";
import { richTrace } from "./fixtures";
import { stagesFor } from "./signal";

const labels = (s: ReturnType<typeof stagesFor>) => s.stages.map((x) => x.label);

describe("stagesFor", () => {
  it("draws the server stages in order, labelled, with offsets from start_ms", () => {
    const s = stagesFor(richTrace(), false);
    expect(labels(s)).toEqual(["preprocess", "screen", "route", "memory", "skills", "tier", "preflight", "execute", "synthesize", "trace", "memory write"]);
    expect(s.stages.map((x) => x.offsetMs)).toEqual([0, 5, 17, 57, 145, 175, 235, 240, 1440, 2140, 2144]);
    expect(s.stages.find((x) => x.label === "route")?.detail).toBe("companion");
    expect(s.stages.find((x) => x.label === "memory")?.detail).toBe("5 chunks");
    expect(s.stages.find((x) => x.label === "execute")?.detail).toBe("5 calls");
  });

  it("draws a second run after a gap marked with paused_ms", () => {
    const stages = [
      { name: "execute_tool", start_ms: 240, duration_ms: 50, run: 1 },
      { name: "await_write_confirmation", start_ms: 290, duration_ms: 0, run: 1 },
      { name: "execute_tool", start_ms: 0, duration_ms: 400, run: 2 },
      { name: "synthesize", start_ms: 400, duration_ms: 300, run: 2 },
    ];
    const s = stagesFor(richTrace({ stages, paused_ms: 12_000 }), false);
    expect(labels(s)).toEqual(["execute", "confirm", "execute", "synthesize"]);
    expect(s.stages.map((x) => x.gapMs)).toEqual([null, null, 12_000, null]);
  });

  it("has no gap in a one-run turn", () => {
    expect(stagesFor(richTrace(), false).stages.every((x) => x.gapMs === null)).toBe(true);
  });

  it("gives a trace opened from history the same offsets as the live one", () => {
    const live = stagesFor(richTrace(), true).stages.map((x) => x.offsetMs);
    const history = stagesFor(richTrace(), false).stages.map((x) => x.offsetMs);
    expect(history).toEqual(live);
  });

  it("falls back to the fields it can prove, with no timing, for a trace without stages", () => {
    const s = stagesFor(richTrace({ stages: undefined }), false);
    expect(labels(s)).toEqual(["screen", "route", "memory", "tier", "tools"]);
    expect(s.stages.every((x) => x.lit && x.offsetMs === null && x.gapMs === null)).toBe(true);
  });

  it("draws screen only when set, memory only with chunks, tier only when set in the fallback", () => {
    const bare = richTrace({ stages: undefined, screen: null, memory_chunks: [], tier: null, tool_calls: [] });
    expect(labels(stagesFor(bare, true))).toEqual(["route"]);
  });

  it("holds the reply as the pending end while streaming, and settles otherwise", () => {
    expect(stagesFor(richTrace(), true)).toMatchObject({ replyPending: true, settled: false });
    expect(stagesFor(richTrace(), false)).toMatchObject({ replyPending: false, settled: true });
  });

  it("takes no client arrival time: only the trace and the streaming flag", () => {
    expect(stagesFor.length).toBe(2);
  });

  it("keeps an unknown node name as its own words", () => {
    const s = stagesFor(richTrace({ stages: [{ name: "inject_routing_context", start_ms: 3, duration_ms: 1, run: 1 }] }), false);
    expect(labels(s)).toEqual(["inject routing context"]);
  });
});
