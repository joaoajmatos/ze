import type { GoalListItem, HeldWriteOut, LoopListItem } from "@myguyze/ze-client";
import type { PendingConfirm } from "@/features/respond-to-confirmation";

export type Decision =
  | { kind: "held_write"; id: string; title: string; at: Date | null; expiresAt: Date | null; held: HeldWriteOut }
  | { kind: "gate"; id: string; goalId: string; title: string; goalTitle: string; at: Date | null; expiresAt: null }
  | { kind: "suspected_loop"; id: string; title: string; at: Date | null; expiresAt: null; loop: LoopListItem }
  | { kind: "chat_confirmation"; id: string; threadId: string; title: string; at: Date | null; expiresAt: Date | null; pending: PendingConfirm };

interface DecisionInput {
  held: HeldWriteOut[];
  goals: GoalListItem[];
  loops: LoopListItem[];
  pendingByThread: Record<string, PendingConfirm[]>;
}

const HELD_KEY = "*";
const date = (s: string | null | undefined) => (s ? new Date(s) : null);

/** Everything waiting on the user, soonest expiry first, then oldest first. */
export function buildDecisions({ held, goals, loops, pendingByThread }: DecisionInput): Decision[] {
  const out: Decision[] = [];
  for (const h of held) {
    out.push({ kind: "held_write", id: h.request_id, title: h.source_name, at: date(h.created_at), expiresAt: date(h.expires_at), held: h });
  }
  for (const g of goals) {
    if (!g.gate_id) continue;
    out.push({ kind: "gate", id: g.gate_id, goalId: g.id, title: g.gate_title ?? g.title, goalTitle: g.title, at: date(g.gate_open_since), expiresAt: null });
  }
  for (const l of loops) {
    if (l.state === "suspected") out.push({ kind: "suspected_loop", id: l.id, title: l.title, at: date(l.created_at), expiresAt: null, loop: l });
  }
  for (const [threadId, list] of Object.entries(pendingByThread)) {
    if (threadId === HELD_KEY) continue;
    for (const p of list) {
      if (p.submitted || (p.kind !== "budget" && p.kind !== "write")) continue;
      out.push({ kind: "chat_confirmation", id: p.id, threadId, title: p.title, at: null, expiresAt: date(p.expiresAt), pending: p });
    }
  }
  return out.sort((a, b) => {
    if (a.expiresAt && b.expiresAt) return a.expiresAt.getTime() - b.expiresAt.getTime();
    if (a.expiresAt) return -1;
    if (b.expiresAt) return 1;
    return (a.at?.getTime() ?? Infinity) - (b.at?.getTime() ?? Infinity);
  });
}
