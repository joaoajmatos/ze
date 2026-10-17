import { useEffect, useRef } from "react";
import { useFrame, useWsStore } from "@/shared/api";
import { usePresenceStore } from "./store";

/**
 * Ze's presence from real signals. Turn phases follow the active thread only: replayed
 * messages, other threads and frames with no thread never move the orb.
 */
export function usePresence(activeThreadId: string | null) {
  const dispatch = usePresenceStore((s) => s.dispatch);
  const { orb, phrase, offline, doneUntil } = usePresenceStore((s) => s.presence);

  const isConnected = useWsStore((s) => s.isConnected);
  const thinking = useWsStore((s) => (activeThreadId ? s.thinkingThreads[activeThreadId] === true : false));
  const typingText = useWsStore((s) => (activeThreadId ? s.typingTextThreads[activeThreadId] ?? null : null));

  useEffect(() => {
    dispatch({ type: isConnected ? "ws_open" : "ws_closed" });
  }, [isConnected, dispatch]);

  useEffect(() => {
    dispatch({ type: "turn_reset" });
  }, [activeThreadId, dispatch]);

  // Busy flag fell with no message or error frame (a confirmation is waiting, the watchdog fired,
  // a retry failed): the turn is over as far as Ze is concerned. A bloom from a message frame stays.
  const wasThinking = useRef(false);
  useEffect(() => {
    if (wasThinking.current && !thinking) dispatch({ type: "turn_end" });
    wasThinking.current = thinking;
  }, [thinking, dispatch]);

  useEffect(() => {
    if (thinking && isConnected) dispatch({ type: "turn_thinking", text: typingText });
  }, [thinking, typingText, isConnected, activeThreadId, dispatch]);

  useEffect(() => {
    if (doneUntil === null) return;
    const id = window.setTimeout(() => dispatch({ type: "settle" }), Math.max(0, doneUntil - Date.now()));
    return () => window.clearTimeout(id);
  }, [doneUntil, dispatch]);

  const mine = (threadId: string | null | undefined) => activeThreadId !== null && threadId === activeThreadId;

  useFrame("typing", (f) => {
    if (mine(f.thread_id)) dispatch({ type: "turn_thinking", text: f.text ?? null });
  });
  useFrame("token", (f) => {
    if (mine(f.thread_id)) dispatch({ type: "turn_token" });
  });
  useFrame("message", (f) => {
    if (f.message.role === "assistant" && mine(f.message.thread_id)) dispatch({ type: "turn_message" });
  });
  useFrame("error", (f) => {
    if (mine(f.thread_id)) dispatch({ type: "turn_error" });
  });

  return { orb, phrase, offline };
}
