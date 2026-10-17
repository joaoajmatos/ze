import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { describeJudgments } from "./judgments";

export interface Readouts {
  totalMs: number;
  model: string;
  systemOne: { requests: number; latencyMs: number; inputTokens: number } | null;
  systemOneText: string | null;
  compaction: string | null;
  resumeRecap: boolean;
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
  return {
    totalMs: trace.total_duration_ms ?? 0,
    model: trace.tier?.model ?? "not recorded",
    systemOne,
    systemOneText: systemOne
      ? `System One: ${systemOne.requests} request${systemOne.requests === 1 ? "" : "s"}, ${systemOne.latencyMs} ms, ${systemOne.inputTokens.toLocaleString("en-US")} input tokens`
      : null,
    compaction,
    resumeRecap: Boolean(trace.resume_recap_applied),
  };
}
