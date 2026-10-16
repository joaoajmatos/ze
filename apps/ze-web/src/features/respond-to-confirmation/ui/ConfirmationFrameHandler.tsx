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
    usePendingConfirms.getState().upsert(toPending(frame, frameThread));
    if (frameThread !== current) setThreadAttention(frameThread, true);
  });

  useFrame("confirm_cancel", (frame) => {
    usePendingConfirms.getState().cancel(frame.id);
  });

  // The server sends no confirm_cancel for a normal answer; resuming the thread is the acknowledgement.
  const acknowledge = (threadId: string | null | undefined) =>
    usePendingConfirms.getState().acknowledge(threadId ?? useSession.getState().threadId);
  useFrame("typing", (frame) => acknowledge(frame.thread_id));
  useFrame("token", (frame) => acknowledge(frame.thread_id));
  useFrame("message", (frame) => acknowledge(frame.message.thread_id));

  return null;
}
