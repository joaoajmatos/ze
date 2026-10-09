import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { FeedbackKind, FeedbackRating, MessageFeedback } from "../model/types";

const KIND: Record<FeedbackRating, FeedbackKind> = {
  up: "thumbs_up",
  down: "thumbs_down",
  none: "cleared",
};

export function applyRating(
  view: MessageFeedback,
  rating: FeedbackRating,
  now = new Date().toISOString(),
): MessageFeedback {
  return {
    ...view,
    current: rating === "none" ? null : rating,
    history: [...(view.history ?? []), { kind: KIND[rating], occurred_at: now }],
  };
}

type Snapshot = [readonly unknown[], MessageFeedback[] | undefined][];

export function patchFeedback(
  queryClient: QueryClient,
  messageId: string,
  patch: (view: MessageFeedback) => MessageFeedback,
): Snapshot {
  const snapshot = queryClient.getQueriesData<MessageFeedback[]>({
    queryKey: queryKeys.messageFeedbackAll,
  });
  queryClient.setQueriesData<MessageFeedback[]>(
    { queryKey: queryKeys.messageFeedbackAll },
    (items) => items?.map((f) => (f.message_id === messageId ? patch(f) : f)),
  );
  return snapshot;
}

export function restoreFeedback(queryClient: QueryClient, snapshot: Snapshot) {
  for (const [key, data] of snapshot) queryClient.setQueryData(key, data);
}
