/** One vocabulary for how sure Ze is and why: the field marks, rows and cards all read it. */
export type Posture = "told" | "evidenced" | "inferred" | "suspected" | "goal" | "plain";
export type GlyphKind = "told" | "inferred" | "suspected" | "goal";
export type ConcernKind = "loop" | "goal" | "hypothesis" | "relationship" | "reminder";

export interface PostureInput {
  kind: ConcernKind;
  state?: string | null;
  claimKind?: string | null;
  provenance?: string | null;
  /** A hypothesis the user confirmed: evidenced, not told (they confirmed Ze's inference, they did not declare it). */
  confirmed?: boolean;
  /** The record behind the item did not load: nothing is claimed about it. */
  partial?: boolean;
}

export function postureOf(c: PostureInput): Posture {
  if (c.partial) return "plain";
  switch (c.kind) {
    case "goal":
      return "goal";
    case "relationship":
    case "reminder":
      return "plain";
    case "hypothesis":
      if (c.confirmed) return "evidenced";
      return c.claimKind === "suspicion" ? "suspected" : "inferred";
    case "loop":
      if (c.state === "suspected" || c.claimKind === "suspicion") return "suspected";
      if (c.provenance === "user_declared") return "told";
      if (c.claimKind === "inference") return "inferred";
      return "evidenced";
  }
}

export function glyphOf(p: Posture): GlyphKind | null {
  switch (p) {
    case "told":
    case "evidenced":
      return "told";
    case "plain":
      return null;
    default:
      return p;
  }
}

export function chipLabelOf(p: Posture): string | null {
  switch (p) {
    case "told":
      return "you told me";
    case "evidenced":
      return "seen in evidence";
    case "inferred":
      return "asked, not stated";
    case "suspected":
      return "suspected";
    case "goal":
      return "goal";
    case "plain":
      return null;
  }
}

const STATE_WORDS: Record<string, string> = {
  suspected: "suspected",
  active: "active",
  drifting: "drifting",
  closed: "done",
  dropped: "dropped",
  planning: "planning",
  awaiting_gate: "waiting on you",
  paused: "paused",
  completed: "done",
  abandoned: "abandoned",
  upcoming: "upcoming",
  overdue: "overdue",
  fired: "sent",
  open: "open",
  dismissed: "dismissed",
};

function plain(raw: string): string {
  return raw.replace(/_/g, " ").trim();
}

export function stateWords(kind: ConcernKind, state: string | null | undefined): string {
  if (!state) return "";
  if (kind === "hypothesis" && state === "confirmed") return "confirmed by you";
  return STATE_WORDS[state] ?? plain(state);
}

const PROVENANCE_WORDS: Record<string, string> = {
  user_declared: "you told me",
  conversation: "chat",
  ingestion: "ingested",
  graph_recall: "memory",
  live_search: "web search",
  prompt_supplied: "your message",
  synthesized: "worked out by Ze",
};

export function provenanceWords(provenance: string | null | undefined): string {
  if (!provenance) return "";
  return PROVENANCE_WORDS[provenance] ?? plain(provenance);
}
