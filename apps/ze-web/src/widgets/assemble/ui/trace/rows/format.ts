import type { FeedbackKind } from "@/entities/message-feedback";

const KIND_LABEL: Record<FeedbackKind, string> = {
  thumbs_up: "Thumbs up",
  thumbs_down: "Thumbs down",
  cleared: "Rating cleared",
  retry_requested: "Retry requested",
};

export function feedbackKindLabel(kind: FeedbackKind): string {
  return KIND_LABEL[kind];
}

export function formatFeedbackTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const OUTCOME_LABEL: Record<string, string> = {
  approved: "Approved",
  edited: "Edited",
  denied: "Denied",
  timed_out: "Timed out",
  superseded: "Superseded",
  refused: "Refused",
  pre_approved: "Pre-approved",
};

export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABEL[outcome] ?? outcome;
}

export function groupByRound<T extends { round: number }>(items: T[]): [number, T[]][] {
  const byRound = new Map<number, T[]>();
  for (const item of items) {
    byRound.set(item.round, [...(byRound.get(item.round) ?? []), item]);
  }
  return [...byRound.entries()].sort(([a], [b]) => a - b);
}
