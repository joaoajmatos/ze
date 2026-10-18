import { useEffect, useRef } from "react";
import { useConnectionState, useWsStore } from "@/shared/api";
import { usePresenceStore } from "./store";

/**
 * Ze's presence from real signals. Turn frames reach the orb through `features/turn-stream`, for the
 * active thread only; here it follows the connection and the thread's busy flag.
 */
export function usePresence(activeThreadId: string | null) {
  const dispatch = usePresenceStore((s) => s.dispatch);
  const { orb, phrase, offline, doneUntil } = usePresenceStore((s) => s.presence);

  const isConnected = useWsStore((s) => s.isConnected);
  const thinking = useWsStore((s) => (activeThreadId ? s.thinkingThreads[activeThreadId] === true : false));
  const typingText = useWsStore((s) => (activeThreadId ? s.typingTextThreads[activeThreadId] ?? null : null));

  // A displaced window is not offline: another window has the connection, so the orb rests instead of showing an error.
  const connection = useConnectionState();
  useEffect(() => {
    if (connection === "displaced") {
      dispatch({ type: "ws_open" });
      dispatch({ type: "turn_reset" });
      return;
    }
    dispatch({ type: connection === "online" ? "ws_open" : "ws_closed" });
  }, [connection, dispatch]);

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

  return { orb, phrase, offline };
}
