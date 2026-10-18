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

  it("reads total, model, compaction span and the recap, and no money", () => {
    const r = readoutsFor(richTrace());
    expect(r.toolMs).toBe(4200);
    expect(r.model).toBe("anthropic/claude-sonnet");
    expect(r.compaction).toBe("messages 0–6 summarised");
    expect(r.resumeRecap).toBe(true);
    expect(JSON.stringify(r)).not.toMatch(/\$|usd|cost/i);
  });

  it("says 'not recorded' without a tier, and has no System One line without judgments", () => {
    const r = readoutsFor(richTrace({ tier: null, judgments: [], compaction: null, resume_recap_applied: false }));
    expect(r.model).toBe("not recorded");
    expect(r.systemOneText).toBeNull();
    expect(r.compaction).toBeNull();
  });
});
