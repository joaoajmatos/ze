import type { ThreadMessage as Message } from "@/entities/conversation";

export interface Exchange {
  /** The user line, or the first reply's id when Ze spoke unprompted. */
  id: string;
  user: Message | null;
  replies: Message[];
  /** An assistant message with no user line before it: a proactive message, a gate reply, a recap, the onboarding view. */
  unprompted: boolean;
}

/** Groups a thread into exchanges. A reply that a retry replaced is not shown. */
export function groupExchanges(messages: Message[]): Exchange[] {
  const exchanges: Exchange[] = [];
  for (const message of messages) {
    if (message.role === "user") {
      exchanges.push({ id: message.id, user: message, replies: [], unprompted: false });
      continue;
    }
    if (message.replaced_by) continue;
    const last = exchanges.at(-1);
    if (last) last.replies.push(message);
    else exchanges.push({ id: message.id, user: null, replies: [message], unprompted: true });
  }
  return exchanges;
}

const SPAN: Record<string, 4 | 6 | 8 | 12> = {
  headline: 12,
  claim_card: 4,
  claim_timeline: 12,
  chart: 8,
  table: 8,
};

/** Grid columns of 12 for a component on the desktop canvas; the overlay and phones use all 12. */
export function spanOf(type: string, compact: boolean): 4 | 6 | 8 | 12 {
  if (compact) return 12;
  return SPAN[type] ?? 6;
}

export function componentType(component: unknown): string {
  const type = (component as { type?: unknown } | null)?.type;
  return typeof type === "string" ? type : "unknown";
}

/** `A·01`: the instrument id of the nth module on the canvas (DESIGN.md: only the Assemble canvas carries ids). */
export function instrumentId(n: number): string {
  return `A·${String(n).padStart(2, "0")}`;
}
