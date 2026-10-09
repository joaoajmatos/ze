import { getMessageFeedback, setMessageFeedback } from "@myguyze/ze-client";
import type { MessageFeedback, SetFeedbackArgs } from "../model/types";

export async function fetchMessageFeedback(ids: string[]): Promise<MessageFeedback[]> {
  const { data, error } = await getMessageFeedback({ query: { ids } });
  if (error || !data) throw error ?? new Error("feedback unavailable");
  return data.items;
}

export async function putMessageFeedback({
  messageId,
  rating,
  idempotencyKey,
}: SetFeedbackArgs): Promise<MessageFeedback> {
  const { data, error } = await setMessageFeedback({
    path: { message_id: messageId },
    body: { rating, idempotency_key: idempotencyKey },
  });
  if (error || !data) throw error ?? new Error("feedback not saved");
  return data;
}
