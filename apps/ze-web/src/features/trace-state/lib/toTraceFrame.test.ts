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
      tool_duration_ms: 450,
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
      tool_duration_ms: 0,
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
      tool_duration_ms: 0,
      tier,
    } as MessageTraceResponse;
    expect(toTraceFrame("msg-3", trace, "t").tier).toEqual(tier);
  });

  it("carries the screen trace", () => {
    const screen = { origin: "chat_about" as const, place: "doing", subject: ["Workflow · Weekly report"], selection_count: 0, visible_count: 0, canvas_count: 0, note_chars: 40, invalid: [], resolvers: [] };
    const trace = { agent: "a", routing_method: "embedding", confidence: 1, score_gap: 0, is_compound: false, subtasks: [], memory_chunks: [], tool_calls: [], tool_duration_ms: 1, screen } as MessageTraceResponse;
    expect(toTraceFrame("m", trace, "t").screen).toEqual(screen);
  });

  it("keeps the extraction confidence of a stored memory chunk", () => {
    const frame = toTraceFrame("m1", { agent: "companion", routing_method: "embedding", confidence: 0.5, score_gap: 0, is_compound: false, subtasks: [], memory_chunks: [{ text: "a", score: 0.9, source: "fact", extraction_confidence: 0.8 }], tool_calls: [], tool_duration_ms: 1 } as never, "t1");
    expect(frame.memory_chunks[0].extraction_confidence).toBe(0.8);
  });

  it("round-trips the 187b telemetry fields to the frame unchanged", () => {
    const telemetry = {
      turn_duration_ms: 2140,
      paused_ms: 300,
      stages: [{ name: "embed_route", start_ms: 12, duration_ms: 30, run: 1 }],
      usage: {
        main_model: "anthropic/claude-sonnet-4-6",
        models: [{ model: "anthropic/claude-sonnet-4-6", calls: 2, prompt_tokens: 9120, completion_tokens: 410, max_prompt_tokens: 5200, cost_usd: 0.0335, estimated: false }],
        context_fill: 0.026,
        context_window: 200000,
        estimated: false,
        system_one_tokens: 1840,
      },
      routing_scores: [{ agent: "calendar", score: 0.83 }],
      routing_thresholds: { threshold: 0.78, gap: 0.05 },
      telemetry_partial: true,
      tool_calls: [{ name: "list_events", result_snippet: "", duration_ms: 312, success: true, call_id: "9f", start_offset_ms: 640 }],
      judgments: [{ question_id: "agent", kind: "choice", latency_ms: 1, surface: "routing", bar: { name: "choice_trust", value: 0.5 } }],
    };
    const trace = { agent: "a", routing_method: "embedding", confidence: 1, score_gap: 0, is_compound: false, subtasks: [], memory_chunks: [], tool_duration_ms: 312, ...telemetry } as unknown as MessageTraceResponse;
    expect(toTraceFrame("m", trace, "t")).toMatchObject(telemetry);
  });
});
