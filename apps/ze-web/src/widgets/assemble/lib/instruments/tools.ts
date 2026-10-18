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
  parked: "waiting for you",
};

export interface ToolMark {
  /** The call's `call_id`; the list position for a row from before 187b. */
  id: string;
  name: string;
  /** Start within the lane: `start_offset_ms` when recorded, else the cumulative duration of the lane's earlier calls. */
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
  /** The lane's own length in ms. */
  span: number;
  /** Every call in the lane was placed by its recorded start. */
  timed: boolean;
}

const MIN_WIDTH = 24;

/** A later row with the same `call_id` replaces the earlier one in place (a parked call becomes its approved run). */
function byCallId(calls: Call[]): Call[] {
  const out: Call[] = [];
  for (const c of calls) {
    const at = c.call_id ? out.findIndex((o) => o.call_id === c.call_id) : -1;
    if (at >= 0) out[at] = c;
    else out.push(c);
  }
  return out;
}

/**
 * Lanes by owning agent, the reply's agent first, calls in `call_index` order. A call is placed by its
 * `start_offset_ms`; a call without one (a trace stored before 187b) starts where the earlier ones in its lane ended,
 * and the lane then has its own axis. A live row with no offset yet reads "returned". A call without an `agent`
 * joins the reply's lane.
 */
export function toolLanes(calls: Call[] | undefined, replyAgent: string, partial: boolean): ToolLane[] {
  const list = byCallId(calls ?? []).map((c, i) => ({ c, i }));
  list.sort((a, b) => (a.c.call_index ?? a.i) - (b.c.call_index ?? b.i) || a.i - b.i);
  const hasAgents = list.some(({ c }) => c.agent);
  const byAgent = new Map<string, ToolMark[]>();
  const cursor = new Map<string, number>();
  const timed = new Map<string, boolean>();
  for (const { c, i } of list) {
    const agent = hasAgents ? (c.agent ?? replyAgent) : replyAgent;
    const offset = c.start_offset_ms ?? null;
    const returned = partial && offset === null;
    const parked = c.gate === "parked";
    const x = offset ?? cursor.get(agent) ?? 0;
    const w = returned ? 0 : Math.max(c.duration_ms, MIN_WIDTH);
    const gate = c.gate && GATE_WORDS[c.gate] ? c.gate : null;
    const mark: ToolMark = {
      id: c.call_id ?? String(i),
      name: c.name,
      x,
      w,
      durationMs: c.duration_ms,
      irreversible: c.reversibility === "irreversible",
      gate,
      gateWords: gate ? GATE_WORDS[gate] : null,
      failed: !returned && !parked && c.success === false,
      note: c.access === "delegate" ? "includes the delegate's calls" : null,
      returned,
      effect: c.effect_phrase ?? null,
    };
    byAgent.set(agent, [...(byAgent.get(agent) ?? []), mark]);
    cursor.set(agent, Math.max(cursor.get(agent) ?? 0, x + (returned ? 0 : c.duration_ms)));
    timed.set(agent, (timed.get(agent) ?? true) && offset !== null);
  }
  const agents = [...byAgent.keys()].sort((a, b) => (a === replyAgent ? -1 : b === replyAgent ? 1 : 0));
  return agents.map((agent) => ({ agent, calls: byAgent.get(agent)!, span: cursor.get(agent) ?? 0, timed: timed.get(agent) ?? false }));
}
