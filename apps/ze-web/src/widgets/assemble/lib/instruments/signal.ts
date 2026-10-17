import type { WsTraceUpdateFrame } from "@myguyze/ze-client";

export type StageKey = "screen" | "route" | "memory" | "tier" | "tools";

export interface Stage {
  key: StageKey;
  label: string;
  detail: string | null;
  /** Milliseconds from the send to this stage reaching the client; null when not recorded (history). */
  offsetMs: number | null;
  lit: boolean;
}

export interface SignalPath {
  stages: Stage[];
  /** The reply is still coming: the strip ends in an open point. */
  replyPending: boolean;
  settled: boolean;
  totalMs: number | null;
}

type Arrivals = Record<string, number>;

/**
 * The stages of the turn the trace can prove, in pipeline order. A stage appears only when its data arrived,
 * because memory and tier may never come. Preprocess, skills, correlate, surface, synthesize and the memory
 * write are not reported by the trace and are never drawn.
 */
export function stagesFor(
  trace: Partial<WsTraceUpdateFrame>,
  arrivals: Arrivals | undefined,
  sentAt: number | null,
  streaming: boolean,
): SignalPath {
  const at = (key: string): number | null => (arrivals && sentAt !== null && key in arrivals ? arrivals[key] - sentAt : null);
  const stages: Stage[] = [];
  if (trace.screen) stages.push({ key: "screen", label: "screen", detail: null, offsetMs: at("screen"), lit: true });
  if (trace.agent) stages.push({ key: "route", label: "route", detail: trace.agent, offsetMs: at("route"), lit: true });
  const chunks = trace.memory_chunks?.length ?? 0;
  if (chunks > 0) stages.push({ key: "memory", label: "memory", detail: `${chunks} chunk${chunks === 1 ? "" : "s"}`, offsetMs: at("memory"), lit: true });
  if (trace.tier) stages.push({ key: "tier", label: "tier", detail: trace.tier.tier, offsetMs: at("tier"), lit: true });
  const calls = trace.tool_calls?.length ?? 0;
  if (calls > 0) stages.push({ key: "tools", label: "tools", detail: `${calls} call${calls === 1 ? "" : "s"}`, offsetMs: at("tool:0"), lit: true });
  return {
    stages,
    replyPending: streaming,
    settled: !streaming,
    totalMs: !streaming && trace.total_duration_ms ? trace.total_duration_ms : null,
  };
}
