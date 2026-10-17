import { listMessages } from "@myguyze/ze-client";
import type { MessageSchema as Message } from "@myguyze/ze-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { send } from "@/shared/api";

export function useMessages(threadId: string) {
  const [messages, setMessages] = useState<Map<string, Message>>(new Map());
  const loadedThreadRef = useRef<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  useEffect(() => {
    if (loadedThreadRef.current !== threadId) {
      setMessages(new Map());
      setHistoryLoaded(false);
      loadedThreadRef.current = null;
    }
  }, [threadId]);

  const upsert = useCallback(
    (msg: Message) => {
      if (msg.thread_id && msg.thread_id !== threadId) return;
      setMessages((prev) => {
        const next = new Map(prev);
        next.set(String(msg.id), msg);
        return next;
      });
    },
    [threadId],
  );

  const remove = useCallback((id: string) => {
    setMessages((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const edit = useCallback((id: string, text?: string, components?: Message["components"]) => {
    setMessages((prev) => {
      const existing = prev.get(id);
      if (!existing) return prev;
      const next = new Map(prev);
      next.set(id, {
        ...existing,
        ...(text !== undefined && { text }),
        ...(components !== undefined && { components }),
      });
      return next;
    });
  }, []);

  const loadHistory = useCallback(async (): Promise<Message[] | null> => {
    if (loadedThreadRef.current === threadId) return null;
    loadedThreadRef.current = threadId;

    try {
      const { data: history } = await listMessages({
        query: { thread_id: threadId, limit: 200 },
      });
      if (!history) {
        setHistoryLoaded(true);
        return null;
      }
      setMessages(new Map(history.map((msg) => [String(msg.id), msg])));
      setHistoryLoaded(true);

      const unread = history
        .filter((m) => m.role === "assistant" && !m.read && m.id)
        .map((m) => String(m.id));
      if (unread.length > 0) send({ type: "ack", ids: unread });
      return history;
    } catch {
      loadedThreadRef.current = null;
      return null;
    }
  }, [threadId]);

  const reload = useCallback(async (): Promise<Message[] | null> => {
    loadedThreadRef.current = null;
    return loadHistory();
  }, [loadHistory]);

  const sorted = useMemo(
    () =>
      [...messages.values()].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      ),
    [messages],
  );

  return { messages: sorted, historyLoaded, upsert, remove, edit, loadHistory, reload };
}
