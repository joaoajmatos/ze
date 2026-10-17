import type { WsTraceUpdateFrame } from "@myguyze/ze-client";

type Call = WsTraceUpdateFrame["tool_calls"][number];

export const GATE_WORDS: Record<string, string | null> = {
  none: null,
  approved: "approved",
  pre_approved: "pre-approved",
  denied: "denied",
  refused: "refused",
  refused_over_cap: "refused (over the cap)",
  expired: "timed out",
  duplicate: "not repeated",
};

export interface ToolMark {
  name: string;
  /** Start within its own lane: the cumulative duration of the lane's earlier calls. */
  x: number;
  w: number;
  durationMs: number;
  irreversible: boolean;
  gate: string | null;
  gateWords: string | null;
  failed: boolean;
  note: string | null;
  /** A live call: only that it returned is known. */
  returned: boolean;
  effect: string | null;
}

export interface ToolLane {
  agent: string;
  calls: ToolMark[];
  /** The lane's own length in ms; lanes share no axis. */
  span: number;
}

const MIN_WIDTH = 24;

/**
 * Lanes by owning agent, the reply's agent first, calls in `call_index` order. Each lane has its own axis:
 * start times are not recorded, so a call starts where the earlier ones in its lane ended. Lanes are never
 * scaled against the turn's total. Without `agent` on the wire there is one lane in list order.
 */
export function toolLanes(calls: Call[] | undefined, replyAgent: string, partial: boolean): ToolLane[] {
  const list = (calls ?? []).map((c, i) => ({ c: c as Call & { agent?: string | null; call_index?: number | null }, i }));
  list.sort((a, b) => (a.c.call_index ?? a.i) - (b.c.call_index ?? b.i) || a.i - b.i);
  const hasAgents = list.some(({ c }) => c.agent);
  const byAgent = new Map<string, ToolMark[]>();
  const cursor = new Map<string, number>();
  for (const { c } of list) {
    const agent = hasAgents ? (c.agent ?? replyAgent) : replyAgent;
    const x = cursor.get(agent) ?? 0;
    const w = partial ? 0 : Math.max(c.duration_ms, MIN_WIDTH);
    const gate = c.gate && GATE_WORDS[c.gate] ? c.gate : null;
    const mark: ToolMark = {
      name: c.name,
      x,
      w,
      durationMs: c.duration_ms,
      irreversible: c.reversibility === "irreversible",
      gate,
      gateWords: gate ? GATE_WORDS[gate] : null,
      failed: !partial && c.success === false,
      note: c.access === "delegate" ? "includes the delegate's calls" : null,
      returned: partial,
      effect: c.effect_phrase ?? null,
    };
    byAgent.set(agent, [...(byAgent.get(agent) ?? []), mark]);
    cursor.set(agent, x + (partial ? 0 : c.duration_ms));
  }
  const agents = [...byAgent.keys()].sort((a, b) => (a === replyAgent ? -1 : b === replyAgent ? 1 : 0));
  return agents.map((agent) => ({ agent, calls: byAgent.get(agent)!, span: cursor.get(agent) ?? 0 }));
}
