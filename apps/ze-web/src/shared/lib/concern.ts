import type { PriorityOverrideSchema } from "@myguyze/ze-client";
import { stateWords, type ConcernKind } from "./claim-posture";

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

/** State in the user's words; a stuck goal is "stuck", not "active". */
export function concernStateWords(c: Pick<Concern, "kind" | "state" | "slipped">): string {
  if (c.kind === "goal" && c.slipped) return "stuck";
  return stateWords(c.kind, c.state);
}
