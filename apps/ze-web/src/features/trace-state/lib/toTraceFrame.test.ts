import { describe, expect, it } from "vitest";
import type { MessageTraceResponse } from "@myguyze/ze-client";
import { toTraceFrame } from "./toTraceFrame";

describe("toTraceFrame", () => {
  it("maps REST trace response to WS trace frame", () => {
    const trace: MessageTraceResponse = {
      agent: "companion",
      routing_method: "embedding",
      confidence: 0.94,
      score_gap: 0.31,
      is_compound: false,
      subtasks: [],
      memory_chunks: [{ text: "User prefers concise answers", score: 0.91, source: "fact" }],
      tool_calls: [{ name: "search_web", result_snippet: "ok", duration_ms: 120, success: true }],
      total_duration_ms: 450,
      skills_used: [],
      conductor_hint: null,
      conductor_ledger: [],
      judgments: [],
      sources: [{ url: "https://example.com/a", title: "A" }],
    };

    expect(toTraceFrame("msg-1", trace, "thread-a")).toEqual({
      type: "trace_update",
      thread_id: "thread-a",
      message_id: "msg-1",
      ...trace,
      workspace: undefined,
    });
  });

  it("carries the write confirmation outcomes through", () => {
    const outcome = {
      request_id: "req-1",
      round: 1,
      item_id: "c1",
      agent: "calendar",
      tool: "delete_event",
      effect: "deleted a calendar event",
      summary: "Dentist",
      outcome: "approved" as const,
    };
    const frame = toTraceFrame(
      "msg-1",
      { write_confirmations: [outcome] } as unknown as MessageTraceResponse,
      "thread-a",
    ) as unknown as { write_confirmations: unknown[] };
    expect(frame.write_confirmations).toEqual([outcome]);
  });
});
