import { describe, expect, it } from "vitest";
import { richTrace } from "./fixtures";
import { readoutsFor } from "./readouts";

describe("readoutsFor", () => {
  it("counts one System One request per surface group, not per row", () => {
    const r = readoutsFor(richTrace());
    // routing (agent), tier (needs_deep_reasoning), intake (commitment+family+intake_outcome share one request)
    expect(r.systemOne).toEqual({ requests: 3, latencyMs: 300 + 150 + 420, inputTokens: 800 + 400 + 900 });
    expect(r.systemOneText).toBe("System One: 3 requests, 870 ms, 2,100 input tokens");
  });

  it("does not count 8 for a six-row intake group, intake_outcome and one routing row", () => {
    const rows = ["commitment", "family", "biography", "is_open_concern", "explicit_declaration", "resolves_existing"].map((id) => ({ question_id: id, kind: "noul", latency_ms: 420, model: "m", input_tokens: 900 }));
    const t = richTrace({
      judgments: [...rows, { question_id: "intake_outcome", kind: "choice", latency_ms: 420, answer: "hold:trivial" }, { question_id: "agent", kind: "choice", latency_ms: 200, model: "r", input_tokens: 500 }] as never,
    });
    expect(readoutsFor(t).systemOne).toEqual({ requests: 2, latencyMs: 620, inputTokens: 1400 });
  });

  it("reads the total, active and tool time from the server", () => {
    const r = readoutsFor(richTrace({ turn_duration_ms: 9000, paused_ms: 3000, tool_duration_ms: 4200 }));
    expect(r.total).toEqual({ ms: 9000, partial: false });
    expect(r.activeMs).toBe(6000);
    expect(r.toolMs).toBe(4200);
  });

  it("marks the total partial when the recorder lost the start of the turn", () => {
    expect(readoutsFor(richTrace({ telemetry_partial: true })).total).toEqual({ ms: 6000, partial: true });
  });

  it("has no total or active time for a trace before 187b", () => {
    const r = readoutsFor(richTrace({ turn_duration_ms: null, usage: null, stages: undefined }));
    expect(r.total).toBeNull();
    expect(r.activeMs).toBeNull();
    expect(r.toolMs).toBe(4200);
  });

  it("sums tokens and cost over the models, and reads the context fill from usage", () => {
    const r = readoutsFor(richTrace());
    expect(r.usage).toMatchObject({ promptTokens: 9920, completionTokens: 500, costUsd: 0.0356, estimated: false, systemOneTokens: 1840 });
    expect(r.usage?.fill).toEqual({ value: 0.026, bar: 0.026 });
    expect(r.model).toBe("anthropic/claude-sonnet");
  });

  it("clamps the fill bar at full while keeping the real number", () => {
    const usage = { ...richTrace().usage!, context_fill: 1.4 };
    expect(readoutsFor(richTrace({ usage })).usage?.fill).toEqual({ value: 1.4, bar: 1 });
  });

  it("flags estimated usage", () => {
    const usage = { ...richTrace().usage!, estimated: true };
    expect(readoutsFor(richTrace({ usage })).usage?.estimated).toBe(true);
  });

  it("shows the model name only when usage is null", () => {
    const r = readoutsFor(richTrace({ usage: null }));
    expect(r.usage).toBeNull();
    expect(r.model).toBe("anthropic/claude-sonnet");
  });

  it("reads the compaction span and the recap", () => {
    const r = readoutsFor(richTrace());
    expect(r.compaction).toBe("messages 0–6 summarised");
    expect(r.resumeRecap).toBe(true);
  });

  it("says 'not recorded' without a tier, and has no System One line without judgments", () => {
    const r = readoutsFor(richTrace({ tier: null, usage: null, judgments: [], compaction: null, resume_recap_applied: false }));
    expect(r.model).toBe("not recorded");
    expect(r.systemOneText).toBeNull();
    expect(r.compaction).toBeNull();
  });
});
