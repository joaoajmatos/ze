import type { Concern } from "@/shared/lib";

export const NOW = new Date("2026-10-17T12:00:00Z");
export const day = (n: number) => new Date(NOW.getTime() + n * 86_400_000);

/** A concern with every field set; tests override what they care about. */
export function concern(id: string, extra: Partial<Concern> = {}): Concern {
  return {
    key: `loop:${id}`, kind: "loop", id, title: `Concern ${id}`, rank: null, computedRank: null, overridden: false, override: null,
    pinned: false, state: "active", claimKind: "fact", provenance: "email", confirmed: false, confidence: 0.7, confidencePrior: null,
    due: null, dueLabel: null, slipped: false, partial: false, driftRationale: null, sources: [], updatedAt: null, reminderId: null, progress: null,
    ...extra,
  };
}
