import type { FeedbackHistoryItem, FeedbackView, RetryEligibilityResponse } from "@myguyze/ze-client";

export type FeedbackRating = "up" | "down" | "none";
export type FeedbackKind = FeedbackHistoryItem["kind"];
;
export type RetryEligibility = RetryEligibilityResponse;
export type MessageFeedback = FeedbackView;

export interface SetFeedbackArgs {
  messageId: string;
  rating: FeedbackRating;
  idempotencyKey: string;
}
