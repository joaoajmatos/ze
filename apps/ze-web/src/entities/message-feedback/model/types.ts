// Mirrors specs/phases/165-response-feedback-retry/contracts/api.md. Replace with
// the generated @myguyze/ze-client types once `getMessageFeedback` lands.
export type FeedbackRating = "up" | "down" | "none";

export type FeedbackKind = "thumbs_up" | "thumbs_down" | "cleared" | "retry_requested";

export interface FeedbackHistoryItem {
  kind: FeedbackKind;
  occurred_at: string;
}

export interface RetryEligibility {
  available: boolean;
  reason_code: string | null;
  reason_text: string | null;
}

export interface MessageFeedback {
  message_id: string;
  current: "up" | "down" | null;
  history: FeedbackHistoryItem[];
  retry: RetryEligibility;
  replaces: string | null;
  replaced_by: string | null;
  trace_present: boolean;
}

export interface SetFeedbackArgs {
  messageId: string;
  rating: FeedbackRating;
  idempotencyKey: string;
}
