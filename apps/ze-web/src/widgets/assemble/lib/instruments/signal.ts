import type { WsTraceUpdateFrame } from "@myguyze/ze-client";

export interface Stage {
  key: string;
  label: string;
  detail: string | null;
  /** Milliseconds from the turn start, as the server recorded it; null on a trace without stages. */
  offsetMs: number | null;
  lit: boolean;
  /** The first stage of a resumed run: how long the turn waited for you before it. */
  gapMs: number | null;
}

export interface SignalPath {
  stages: Stage[];
  /** The reply is still coming: the strip ends in an open point. */
  replyPending: boolean;
  settled: boolean;
}

const LABEL_OF: Record<string, string> = {
  preprocess: "preprocess",
  resolve_screen: "screen",
  embed_route: "route",
  decompose: "decompose",
  fetch_context: "memory",
  match_skills: "skills",
  choose_tier: "tier",
  preflight: "preflight",
  execute_tool: "execute",
  await_write_confirmation: "confirm",
  correlate: "correlate",
  surface_loops: "surface",
  synthesize: "synthesize",
  record_trace: "trace",
  write_memory: "memory write",
};

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

function detailOf(label: string, trace: Partial<WsTraceUpdateFrame>): string | null {
  if (label === "route") return trace.agent ?? null;
  if (label === "memory") return (trace.memory_chunks?.length ?? 0) > 0 ? plural(trace.memory_chunks!.length, "chunk") : null;
  if (label === "tier") return trace.tier?.tier ?? null;
  if (label === "execute" || label === "tools") return (trace.tool_calls?.length ?? 0) > 0 ? plural(trace.tool_calls!.length, "call") : null;
  return null;
}

/** Without server stages (a trace from before 187b) only the stages the fields prove are drawn, with no timing. */
function stagesFromFields(trace: Partial<WsTraceUpdateFrame>): Stage[] {
  const labels: string[] = [];
  if (trace.screen) labels.push("screen");
  if (trace.agent) labels.push("route");
  if ((trace.memory_chunks?.length ?? 0) > 0) labels.push("memory");
  if (trace.tier) labels.push("tier");
  if ((trace.tool_calls?.length ?? 0) > 0) labels.push("tools");
  return labels.map((label) => ({ key: label, label, detail: detailOf(label, trace), offsetMs: null, lit: true, gapMs: null }));
}

/** The turn's stages in the order the server finished them, offsets from `start_ms`. A resumed run is drawn after a gap of `paused_ms`. */
export function stagesFor(trace: Partial<WsTraceUpdateFrame>, streaming: boolean): SignalPath {
  const recorded = trace.stages ?? [];
  let previousRun = recorded[0]?.run ?? 1;
  const stages: Stage[] =
    recorded.length === 0
      ? stagesFromFields(trace)
      : recorded.map((s) => {
          const run = s.run ?? 1;
          const gapMs = run !== previousRun ? (trace.paused_ms ?? 0) : null;
          previousRun = run;
          const label = LABEL_OF[s.name] ?? s.name.replace(/_/g, " ");
          return { key: label, label, detail: detailOf(label, trace), offsetMs: s.start_ms, lit: true, gapMs };
        });
  return { stages, replyPending: streaming, settled: !streaming };
}
