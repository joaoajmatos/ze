import { useSession } from "@/entities/session";
import { useFrame, useWsStore } from "@/shared/api";
import { toPending, usePendingConfirms } from "../model/pending-store";

/** Keeps every thread's pending confirmation, so a card is there when its thread opens. */
export function ConfirmationFrameHandler() {
  const setThreadThinking = useWsStore((s) => s.setThreadThinking);
  const setThreadAttention = useWsStore((s) => s.setThreadAttention);

  useFrame("confirm_request", (frame) => {
    const current = useSession.getState().threadId;
    const frameThread = frame.thread_id ?? current;
    setThreadThinking(frameThread, false);
    usePendingConfirms.getState().set(toPending(frame, frameThread));
    if (frameThread !== current) setThreadAttention(frameThread, true);
  });

  useFrame("confirm_cancel", (frame) => {
    const frameThread = frame.thread_id ?? useSession.getState().threadId;
    usePendingConfirms.getState().cancel(frameThread, frame.id);
  });

  return null;
}
