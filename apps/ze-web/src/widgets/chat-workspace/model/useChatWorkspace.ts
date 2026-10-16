import type { MessageSchema as Message, WsScreenContext as ScreenContext } from "@myguyze/ze-client";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useMessages } from "@/features/load-chat-history";
import { useConfirmation } from "@/features/respond-to-confirmation";
import { useOnboardingSession } from "@/entities/onboarding-session";
import { useSession } from "@/entities/session";
import { useFrame, useWsStore, send } from "@/shared/api";
import { useSendNotice } from "@/shared/lib";
import { queryKeys } from "@/shared/lib";

const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";

// Longest silence (no reply, typing or token frame) tolerated before the client
// stops waiting on the live connection and checks stored history instead.
export const DELIVERY_WATCHDOG_MS = 120_000;

interface SentMessage {
  text: string;
  workspacePlaced?: { path: string; size: number }[];
}

interface UseChatWorkspaceOptions {
  ephemeral?: boolean;
  active?: boolean;
  context?: ScreenContext;
  threadId?: string;
}

export function useChatWorkspace(options: UseChatWorkspaceOptions = {}) {
  const { ephemeral = false, active = true, context, threadId: threadIdOverride } = options;
  const sessionThreadId = useSession((s) => s.threadId);
  const threadId = threadIdOverride ?? sessionThreadId;
  const queryClient = useQueryClient();
  const { messages: persistedMessages, upsert, remove, edit, loadHistory, reload } = useMessages(threadId);

  const [ephemeralMessages, setEphemeralMessages] = useState<Message[]>([]);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [failedThread, setFailedThread] = useState<string | null>(null);
  const prevActiveRef = useRef(active);
  const messagesRef = useRef(persistedMessages);
  const knownAssistantIdsRef = useRef<Set<string>>(new Set());
  const activityAtRef = useRef(0);
  const awaitingRef = useRef(false);
  const lastSentRef = useRef<SentMessage | null>(null);
  const checkForReplyRef = useRef<() => Promise<boolean>>(async () => false);
  const sessionsInvalidateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const debouncedInvalidateSessions = () => {
    if (sessionsInvalidateTimerRef.current) {
      clearTimeout(sessionsInvalidateTimerRef.current);
    }
    sessionsInvalidateTimerRef.current = setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
    }, 2000);
  };

  useEffect(() => {
    return () => {
      if (sessionsInvalidateTimerRef.current) {
        clearTimeout(sessionsInvalidateTimerRef.current);
      }
    };
  }, []);

  // Typing indicator is derived from per-thread Zustand state so it survives
  // session switches — when you switch back to a processing session the
  // indicator is still visible.
  const isThinking = useWsStore((s) => s.thinkingThreads[threadId] ?? false);
  const typingText = useWsStore((s) => s.typingTextThreads[threadId] ?? null);
  const setThreadThinking = useWsStore((s) => s.setThreadThinking);
  const setThreadTypingText = useWsStore((s) => s.setThreadTypingText);
  const setThreadAttention = useWsStore((s) => s.setThreadAttention);
  const isConnected = useWsStore((s) => s.isConnected);
  const interrupted = useWsStore((s) => s.interruptedThreads[threadId] ?? false);
  const clearThreadInterrupted = useWsStore((s) => s.clearThreadInterrupted);

  // showTyping mirrors isThinking so the chat bubble is visible whenever
  // the backend is processing, regardless of which session was active
  // when the typing frame originally arrived.
  const showTyping = isThinking;
  const deliveryFailed = failedThread === threadId;

  const { pendingConfirms, respond: respondToConfirm, clear: clearConfirm } = useConfirmation(
    ephemeral,
    threadId,
  );

  const messages = ephemeral ? ephemeralMessages : persistedMessages;

  useEffect(() => {
    if (ephemeral && active && !prevActiveRef.current) {
      setEphemeralMessages([]);
    }
    prevActiveRef.current = active;
  }, [active, ephemeral]);

  useEffect(() => {
    if (!ephemeral && isConnected && active) {
      void loadHistory();
    }
  }, [ephemeral, isConnected, active, threadId, loadHistory]);

  useEffect(() => {
    messagesRef.current = persistedMessages;
  });

  // Reloads stored history and reports whether an assistant reply arrived that
  // this client had not seen when the wait began.
  async function checkForReply(): Promise<boolean> {
    if (ephemeral) return false;
    const history = await reload();
    return (
      history?.some(
        (m) => m.role === "assistant" && m.id && !knownAssistantIdsRef.current.has(String(m.id)),
      ) ?? false
    );
  }

  useEffect(() => {
    checkForReplyRef.current = checkForReply;
  });

  // Bounded wait: whatever flipped the thread to thinking, it ends in a visible
  // reply or a visible failure, never an indefinite spinner.
  useEffect(() => {
    if (!isThinking || !active) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    knownAssistantIdsRef.current = new Set(
      messagesRef.current.filter((m) => m.role === "assistant" && m.id).map((m) => String(m.id)),
    );
    activityAtRef.current = Date.now();

    const arm = (ms: number) => {
      timer = setTimeout(() => void onDeadline(), ms);
    };
    const onDeadline = async () => {
      const idle = Date.now() - activityAtRef.current;
      if (idle < DELIVERY_WATCHDOG_MS) {
        arm(DELIVERY_WATCHDOG_MS - idle);
        return;
      }
      const replied = await checkForReplyRef.current();
      if (cancelled) return;
      stopThinking();
      if (!replied) setFailedThread(threadId);
    };
    arm(DELIVERY_WATCHDOG_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stopThinking only closes over threadId and stable setters
  }, [isThinking, active, threadId]);

  // The socket dropped mid-turn. Once reconnected, the stored reply either is in
  // history or the turn is lost; say so instead of leaving a silent empty composer.
  useEffect(() => {
    if (!interrupted || !isConnected || !active) return;
    clearThreadInterrupted(threadId);
    void checkForReplyRef.current().then((replied) => {
      if (!replied) setFailedThread(threadId);
    });
  }, [interrupted, isConnected, active, threadId, clearThreadInterrupted]);

  useFrame("typing", (frame) => {
    const frameThread = frame.thread_id ?? null;
    if (frameThread && frameThread !== threadId) {
      // Another thread is thinking — update its global state.
      // The backend stores the user message before sending typing, so the
      // session exists in the DB now — invalidate the sessions list.
      setThreadThinking(frameThread, true);
      setThreadTypingText(frameThread, frame.text ?? null);
      debouncedInvalidateSessions();
      return;
    }
    // Typing for our own thread.
    activityAtRef.current = Date.now();
    setThreadTypingText(threadId, frame.text ?? null);
    debouncedInvalidateSessions();
  });

  function stopThinking() {
    awaitingRef.current = false;
    setThreadThinking(threadId, false);
    setThreadTypingText(threadId, null);
    setStreamingText(null);
  }

  useFrame("message", (frame) => {
    const frameThread = frame.message.thread_id ?? null;

    if (frameThread && frameThread !== threadId) {
      // Message arrived for a different thread — clear its thinking and signal attention.
      setThreadThinking(frameThread, false);
      setThreadTypingText(frameThread, null);
      if (frame.message.role === "assistant") {
        // Only set attention if this session isn't the one currently open.
        const activeThread = useSession.getState().threadId;
        if (frameThread !== activeThread) {
          setThreadAttention(frameThread, true);
        }
        void queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
      }
      return;
    }

    // Message for our own thread — clear any stale attention.
    setThreadAttention(threadId, false);

    if (!active) {
      // Closed overlay or hidden page: keep the reply, never leave the spinner stuck.
      if (!ephemeral) upsert(frame.message);
      stopThinking();
      return;
    }

    if (frame.onboarding) {
      useOnboardingSession.getState().setSession(
        frame.onboarding.session_id,
        frame.onboarding.completed,
      );
    }

    if (ephemeral) {
      setEphemeralMessages((prev) => [...prev, frame.message]);
    } else {
      upsert(frame.message);
      if (frame.message.role === "assistant" && !frame.message.read && frame.message.id) {
        send({ type: "ack", ids: [frame.message.id] });
      }
      if (frame.message.role === "assistant") {
        void queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
      }
    }

    setFailedThread(null);
    stopThinking();
  });

  useFrame("edit", (frame) => {
    if (!active || ephemeral) return;
    edit(frame.id, frame.text ?? undefined, frame.components as Message["components"]);
  });

  useFrame("token", (frame) => {
    const frameThread = frame.thread_id ?? null;
    if (frameThread && frameThread !== threadId) return;
    if (!active) return;
    activityAtRef.current = Date.now();
    setStreamingText((prev) => (prev ?? "") + (frame.text ?? ""));
  });

  useFrame("error", (frame) => {
    const frameThread = frame.thread_id ?? null;
    if (frameThread && frameThread !== threadId) {
      setThreadThinking(frameThread, false);
      setThreadTypingText(frameThread, null);
      return;
    }
    // An untagged error belongs to whichever hook just sent; the others must not
    // unlock a turn that is still running.
    if (!frameThread && !awaitingRef.current) return;
    if (!active) return;
    const wasAwaiting = awaitingRef.current;
    stopThinking();
    if (wasAwaiting) setFailedThread(threadId);
  });

  function sendMessage(
    text: string,
    workspacePlaced?: { path: string; size: number }[],
    { resend = false }: { resend?: boolean } = {},
  ): boolean {
    const trimmed = text.trim();
    if (!trimmed || isThinking) return false;

    const mergedContext = {
      ...context,
      ...(workspacePlaced?.length ? { workspace_placed: workspacePlaced } : {}),
    } as typeof context;

    const sent = send({
      type: "message",
      text: trimmed,
      thread_id: threadId,
      context: mergedContext,
    });
    if (!sent) {
      useSendNotice.getState().showNotice(NOT_CONNECTED_NOTICE);
      return false;
    }

    lastSentRef.current = { text: trimmed, workspacePlaced };
    awaitingRef.current = true;
    setFailedThread(null);

    // A resend keeps the original bubble unless a history reload dropped it.
    const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
    if (!ephemeral && !(resend && lastUser?.text === trimmed)) {
      upsert({
        id: crypto.randomUUID(),
        role: "user",
        text: trimmed,
        components: [],
        read: true,
        created_at: new Date().toISOString(),
        thread_id: threadId,
      });
    }

    setThreadThinking(threadId, true);
    return true;
  }

  function retry(): boolean {
    const last = lastSentRef.current;
    if (!last) return false;
    return sendMessage(last.text, last.workspacePlaced, { resend: true });
  }

  function resetInteraction() {
    setThreadThinking(threadId, false);
    setThreadTypingText(threadId, null);
    clearConfirm();
  }

  return {
    threadId,
    messages,
    showTyping,
    typingText,
    streamingText,
    isThinking,
    isConnected,
    deliveryFailed,
    pendingConfirms,
    sendMessage,
    retry,
    removeMessage: remove,
    respondToConfirm,
    resetInteraction,
  };
}
