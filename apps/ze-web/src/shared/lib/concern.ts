import type { PriorityOverrideSchema } from "@myguyze/ze-client";
import { chipLabelOf, glyphOf, postureOf, stateWords, type Posture } from "./claim-posture";

export type ConcernKind = "loop" | "goal" | "hypothesis" | "relationship" | "reminder";

export interface Concern {
  /** `${kind}:${id}`, unique across kinds. */
  key: string;
  kind: ConcernKind;
  id: string;
  title: string;
  rank: number | null;
  computedRank: number | null;
  overridden: boolean;
  override: PriorityOverrideSchema | null;
  pinned: boolean;
  state: string | null;
  claimKind: string | null;
  provenance: string | null;
  confirmed: boolean;
  /** null means "not a claim": goals, relationships, reminders and records that failed to load. */
  confidence: number | null;
  /** Where confidence stood before it last changed; the trail is drawn only when present. */
  confidencePrior: number | null;
  due: Date | null;
  dueLabel: "drift deadline" | "reminder" | null;
  slipped: boolean;
  /** The snapshot named the item but its record did not load: title only. */
  partial: boolean;
  driftRationale: string | null;
  sources: string[];
  updatedAt: Date | null;
  reminderId: string | null;
  progress: { done: number; total: number; next: string | null; stuckSince: string | null } | null;
}

type PostureSource = Pick<Concern, "kind" | "state" | "claimKind" | "provenance" | "confirmed" | "partial">;

/** The shared posture for a concern: what its record says, and nothing when the record did not load or it is not a claim. */
export function concernPosture(c: PostureSource): Posture {
  if (c.partial || c.kind === "relationship" || c.kind === "reminder") return "plain";
  if (c.kind === "goal") return "goal";
  if (c.state === "suspected") return "suspected";
  if (c.kind === "hypothesis" && c.confirmed) return "evidenced";
  if (c.kind === "loop" && c.provenance === "user_declared" && c.state !== "suspected" && c.claimKind !== "suspicion") return "told";
  return postureOf(c.claimKind, c.kind, c.state);
}

/** The Glyph kind for a posture, or null when the item is not a claim. */
export function concernGlyph(p: Posture): "told" | "inferred" | "suspected" | "goal" | null {
  if (p === "plain") return null;
  return (glyphOf(p) || "told") as "told" | "inferred" | "suspected" | "goal";
}

export function concernChip(p: Posture): string | null {
  return p === "plain" ? null : chipLabelOf(p);
}

/** State in the user's words; a stuck goal is "stuck", not "open". */
export function concernStateWords(c: Pick<Concern, "kind" | "state" | "slipped">): string {
  if (c.kind === "goal" && c.slipped) return "stuck";
  if (c.kind === "hypothesis" && c.state === "confirmed") return "confirmed by you";
  return c.state ? stateWords(c.state) : "";
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
  return PROVENANCE_WORDS[provenance] ?? provenance.replace(/_/g, " ");
}
