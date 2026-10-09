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
