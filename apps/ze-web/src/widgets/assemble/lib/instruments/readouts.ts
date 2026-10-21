import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { describeJudgments } from "./judgments";

export interface UsageReadout {
  promptTokens: number;
  completionTokens: number;
  costUsd: number;
  estimated: boolean;
  /** The real fill (it can pass 1) and the bar's clamped length. */
  fill: { value: number; bar: number } | null;
  systemOneTokens: number;
}

export interface Readouts {
  /** The whole turn, confirmations included; null on a trace from before 187b. */
  total: { ms: number; partial: boolean } | null;
  /** The total minus the time spent waiting for confirmations. */
  activeMs: number | null;
  toolMs: number;
  usage: UsageReadout | null;
  model: string;
  systemOne: { requests: number; latencyMs: number; inputTokens: number } | null;
  systemOneText: string | null;
  compaction: string | null;
  resumeRecap: boolean;
}

function usageOf(usage: WsTraceUpdateFrame["usage"]): UsageReadout | null {
  if (!usage) return null;
  const models = usage.models ?? [];
  const fill = usage.context_fill ?? null;
  return {
    promptTokens: models.reduce((n, m) => n + m.prompt_tokens, 0),
    completionTokens: models.reduce((n, m) => n + m.completion_tokens, 0),
    costUsd: models.reduce((n, m) => n + m.cost_usd, 0),
    estimated: Boolean(usage.estimated) || models.some((m) => m.estimated),
    fill: fill === null ? null : { value: fill, bar: Math.min(Math.max(fill, 0), 1) },
    systemOneTokens: usage.system_one_tokens ?? 0,
  };
}

/** Each System One batch copies its latency, model and tokens onto every row it answered, so a request is counted once per surface group. */
export function readoutsFor(trace: Partial<WsTraceUpdateFrame>): Readouts {
  const { groups } = describeJudgments(trace.judgments);
  const byId = new Map((trace.judgments ?? []).map((j) => [j.question_id, j]));
  let requests = 0;
  let latencyMs = 0;
  let inputTokens = 0;
  for (const group of groups) {
    const first = byId.get(group.rows[0].id);
    if (!first) continue;
    requests += 1;
    latencyMs += first.latency_ms;
    inputTokens += first.input_tokens ?? 0;
  }
  const systemOne = requests > 0 ? { requests, latencyMs, inputTokens } : null;
  const compaction = trace.compaction ? `messages ${trace.compaction.span_start}–${trace.compaction.span_end} summarised` : null;
  const totalMs = trace.turn_duration_ms ?? null;
  return {
    total: totalMs === null ? null : { ms: totalMs, partial: Boolean(trace.telemetry_partial) },
    activeMs: totalMs === null ? null : Math.max(totalMs - (trace.paused_ms ?? 0), 0),
    toolMs: trace.tool_duration_ms ?? 0,
    usage: usageOf(trace.usage),
    model: trace.usage?.main_model ?? trace.tier?.model ?? "not recorded",
    systemOne,
    systemOneText: systemOne
      ? `System One: ${systemOne.requests} request${systemOne.requests === 1 ? "" : "s"}, ${systemOne.latencyMs} ms, ${systemOne.inputTokens.toLocaleString("en-US")} input tokens`
      : null,
    compaction,
    resumeRecap: Boolean(trace.resume_recap_applied),
  };
}
