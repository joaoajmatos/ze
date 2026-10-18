import { useEffect } from "react";
import { useConversation } from "@/entities/conversation";
import { useTraceSocket } from "../model/useTraceSocket";
import { useTraceStore } from "../model/useTraceStore";

const RUNNING = ["awaiting", "thinking", "speaking", "paused"];

/** Mounted once in the shell: feeds the trace store, and starts each turn with no stale pending trace. */
export function TraceFrameHandler() {
  useTraceSocket();
  useEffect(
    () =>
      useConversation.subscribe((state, prev) => {
        for (const [id, t] of Object.entries(state.byThread)) {
          const was = prev.byThread[id]?.turn.phase;
          if (t.turn.phase === "awaiting" && !RUNNING.includes(was ?? "idle")) useTraceStore.getState().resetPending(id);
        }
      }),
    [],
  );
  return null;
}
