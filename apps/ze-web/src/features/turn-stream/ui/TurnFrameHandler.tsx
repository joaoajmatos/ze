import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { loadThreadHistory, useConversation, type ConversationEvent, type ThreadState } from "@/entities/conversation";
import { useOnboardingSession } from "@/entities/onboarding-session";
import { usePresenceStore } from "@/entities/presence";
import { useSession } from "@/entities/session";
import { send, useFrame, useWsStore } from "@/shared/api";
import { queryKeys } from "@/shared/lib";
import { startDeliveryWatchdog } from "../model/watchdog";

const SESSIONS_DEBOUNCE_MS = 2000;
const RUNNING = ["awaiting", "thinking", "speaking"];

/**
 * The one owner of conversation frames. Feeds the reducer, keeps the sessions rail's flags in step with it,
 * and hands the orb its turn signals for the thread on screen.
 */
export function TurnFrameHandler() {
  const queryClient = useQueryClient();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const active = () => useSession.getState().threadId;
  const apply = (event: ConversationEvent) => useConversation.getState().apply(event, { activeThreadId: active() });
  const mine = (threadId: string | null | undefined) => threadId === active();
  const dispatchPresence = usePresenceStore.getState().dispatch;

  const invalidateSessionsSoon = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void queryClient.invalidateQueries({ queryKey: queryKeys.sessions }), SESSIONS_DEBOUNCE_MS);
  };
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  // The sessions rail reads these flags; the store is the truth, they follow it.
  useEffect(() => {
    const sync = (next: Record<string, ThreadState>, prev: Record<string, ThreadState>) => {
      const ws = useWsStore.getState();
      for (const [id, t] of Object.entries(next)) {
        const before = prev[id];
        if (before === t) continue;
        const running = RUNNING.includes(t.turn.phase);
        if (running !== (ws.thinkingThreads[id] ?? false)) ws.setThreadThinking(id, running);
        const text = running ? t.turn.typingText : null;
        if (text !== (ws.typingTextThreads[id] ?? null)) ws.setThreadTypingText(id, text);
        if (t.attention !== (ws.attentionThreads[id] ?? false)) ws.setThreadAttention(id, t.attention);
      }
    };
    return useConversation.subscribe((s, p) => sync(s.byThread, p.byThread));
  }, []);

  useEffect(() => startDeliveryWatchdog({ reload: loadThreadHistory }), []);

  const threadId = useSession((s) => s.threadId);
  useEffect(() => {
    apply({ type: "opened", threadId });
    dispatchPresence({ type: "turn_reset" });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- apply and dispatchPresence read stores at call time
  }, [threadId]);

  useFrame("typing", (f) => {
    apply(f);
    if (mine(f.thread_id)) dispatchPresence({ type: "turn_thinking", text: f.text ?? null });
    invalidateSessionsSoon();
  });
  useFrame("token", (f) => {
    apply(f);
    if (mine(f.thread_id)) dispatchPresence({ type: "turn_token" });
  });
  useFrame("message", (f) => {
    apply(f);
    const m = f.message;
    if (f.onboarding) useOnboardingSession.getState().setSession(f.onboarding.session_id, f.onboarding.completed);
    if (m.role !== "assistant") return;
    if (mine(m.thread_id)) {
      dispatchPresence({ type: "turn_message" });
      if (!m.read && m.id) send({ type: "ack", ids: [m.id] });
    }
    void queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
  });
  useFrame("edit", apply);
  useFrame("error", (f) => {
    apply(f);
    if (mine(f.thread_id)) dispatchPresence({ type: "turn_error" });
  });
  useFrame("message_superseded", apply);
  useFrame("message_rollback", apply);

  // A confirmation is the server waiting for the person, not silence from the server.
  useFrame("confirm_request", (f) => {
    if (!f.thread_id && f.kind === "held") return;
    apply({ type: "paused", threadId: f.thread_id ?? active() });
  });

  return null;
}
