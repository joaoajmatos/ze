import * as sdk from "@myguyze/ze-client";
import type { MessageFeedback, SetFeedbackArgs } from "../model/types";

interface Result<T> {
  data?: T;
  error?: unknown;
}

interface FeedbackSdk {
  getMessageFeedback: (o: {
    query: { ids: string };
  }) => Promise<Result<{ items: MessageFeedback[] }>>;
  setMessageFeedback: (o: {
    path: { message_id: string };
    body: { rating: string; idempotency_key: string };
  }) => Promise<Result<MessageFeedback>>;
}

// Single seam to the generated client; swap for direct imports after T023.
const api = sdk as unknown as FeedbackSdk;

export async function fetchMessageFeedback(ids: string[]): Promise<MessageFeedback[]> {
  const { data, error } = await api.getMessageFeedback({ query: { ids: ids.join(",") } });
  if (error || !data) throw error ?? new Error("feedback unavailable");
  return data.items;
}

export async function putMessageFeedback({
  messageId,
  rating,
  idempotencyKey,
}: SetFeedbackArgs): Promise<MessageFeedback> {
  const { data, error } = await api.setMessageFeedback({
    path: { message_id: messageId },
    body: { rating, idempotency_key: idempotencyKey },
  });
  if (error || !data) throw error ?? new Error("feedback not saved");
  return data;
}
