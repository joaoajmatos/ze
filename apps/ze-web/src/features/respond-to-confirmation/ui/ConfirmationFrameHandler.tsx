import { useSession } from "@/entities/session";
import { useFrame } from "@/shared/api";
import { HELD_KEY, toPending, usePendingConfirms } from "../model/pending-store";

/** Keeps every thread's pending confirmation, so a card is there when its thread opens. */
export function ConfirmationFrameHandler() {
  useFrame("confirm_request", (frame) => {
    const current = useSession.getState().threadId;
    if (!frame.thread_id && frame.kind === "held") {
      usePendingConfirms.getState().upsert(toPending(frame, HELD_KEY));
      return;
    }
    const frameThread = frame.thread_id ?? current;
    usePendingConfirms.getState().upsert(toPending(frame, frameThread));
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
