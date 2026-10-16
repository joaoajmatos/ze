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

  it("carries the rollback record onto the frame", () => {
    const rollback = {
      replaces: "m0",
      entries: [
        { entry_id: "e1", tool: "set_reminder", effect_phrase: "set a reminder", outcome: "undone" as const },
      ],
    };
    const trace = {
      agent: "companion",
      routing_method: "embedding",
      confidence: 1,
      score_gap: 0,
      is_compound: false,
      subtasks: [],
      memory_chunks: [],
      tool_calls: [],
      total_duration_ms: 0,
      rollback,
    } as MessageTraceResponse;
    expect(toTraceFrame("msg-2", trace, "t").rollback).toEqual(rollback);
  });

  it("carries the tier record onto the frame", () => {
    const tier = {
      agent: "companion",
      tier: "simple" as const,
      decided_by: "system_one",
      model: "anthropic/claude-haiku-4-5",
    };
    const trace = {
      agent: "companion",
      routing_method: "embedding",
      confidence: 1,
      score_gap: 0,
      is_compound: false,
      subtasks: [],
      memory_chunks: [],
      tool_calls: [],
      total_duration_ms: 0,
      tier,
    } as MessageTraceResponse;
    expect(toTraceFrame("msg-3", trace, "t").tier).toEqual(tier);
  });
});
