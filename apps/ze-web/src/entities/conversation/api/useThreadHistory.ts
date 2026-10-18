import { listMessages } from "@myguyze/ze-client";
import type { MessageSchema as Message } from "@myguyze/ze-client";
import { useCallback } from "react";
import { send } from "@/shared/api";
import { useConversation } from "../model/store";

const inFlight = new Set<string>();

/** Fetches a thread's stored messages into the store. Returns the history, or null when none came back. */
export async function loadThreadHistory(threadId: string): Promise<Message[] | null> {
  const { apply } = useConversation.getState();
  if (inFlight.has(threadId)) return null;
  inFlight.add(threadId);
  try {
    const { data: history } = await listMessages({ query: { thread_id: threadId, limit: 200 } });
    if (!history) {
      apply({ type: "history_loaded", threadId, messages: [] }, { activeThreadId: threadId });
      return null;
    }
    apply({ type: "history_loaded", threadId, messages: history }, { activeThreadId: threadId });
    const unread = history.filter((m) => m.role === "assistant" && !m.read && m.id).map((m) => String(m.id));
    if (unread.length > 0) send({ type: "ack", ids: unread });
    return history;
  } catch {
    apply({ type: "history_loaded", threadId, messages: [] }, { activeThreadId: threadId });
    return null;
  } finally {
    inFlight.delete(threadId);
  }
}

/** One load per thread unless `reload` is called. */
export function useThreadHistory(threadId: string) {
  const reload = useCallback(() => loadThreadHistory(threadId), [threadId]);
  const loadHistory = useCallback(async (): Promise<Message[] | null> => {
    if (useConversation.getState().byThread[threadId]?.historyLoaded) return null;
    return loadThreadHistory(threadId);
  }, [threadId]);
  return { loadHistory, reload };
}
