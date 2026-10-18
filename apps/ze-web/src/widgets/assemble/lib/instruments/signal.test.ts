import { describe, expect, it } from "vitest";
import { richTrace } from "./fixtures";
import { stagesFor } from "./signal";

const arrivals = { route: 1_400, screen: 1_100, memory: 1_900, tier: 2_300, "tool:0": 2_800 };
const keys = (s: ReturnType<typeof stagesFor>) => s.stages.map((x) => x.key);

describe("stagesFor", () => {
  it("returns the stages in pipeline order with their offsets from the send", () => {
    const s = stagesFor(richTrace(), arrivals, 1_000, false);
    expect(keys(s)).toEqual(["screen", "route", "memory", "tier", "tools"]);
    expect(s.stages.map((x) => x.offsetMs)).toEqual([100, 400, 900, 1_300, 1_800]);
    expect(s.stages.find((x) => x.key === "memory")?.detail).toBe("5 chunks");
    expect(s.stages.find((x) => x.key === "tools")?.detail).toBe("5 calls");
  });

  it("draws screen only when set, memory only with chunks, tier only when set; never a waiting stage", () => {
    const bare = richTrace({ screen: null, memory_chunks: [], tier: null, tool_calls: [] });
    expect(keys(stagesFor(bare, {}, 0, true))).toEqual(["route"]);
  });

  it("has a single-agent turn with no tier and no memory return route and tools only", () => {
    const t = richTrace({ screen: null, memory_chunks: [], tier: null });
    expect(keys(stagesFor(t, {}, 0, false))).toEqual(["route", "tools"]);
  });

  it("holds the reply as the pending end while streaming, and settles with the total", () => {
    expect(stagesFor(richTrace(), arrivals, 1_000, true)).toMatchObject({ replyPending: true, settled: false });
    expect(stagesFor(richTrace(), arrivals, 1_000, false)).toMatchObject({ replyPending: false, settled: true });
  });

  it("draws a history trace settled, every stage lit, with no offsets", () => {
    const s = stagesFor(richTrace(), undefined, null, false);
    expect(keys(s)).toEqual(["screen", "route", "memory", "tier", "tools"]);
    expect(s.stages.every((x) => x.lit && x.offsetMs === null)).toBe(true);
  });

  it("never returns the stages the trace cannot prove", () => {
    const names = keys(stagesFor(richTrace(), arrivals, 0, false));
    for (const banned of ["preprocess", "skills", "correlate", "surface", "synthesize", "write"]) expect(names).not.toContain(banned);
  });
});
