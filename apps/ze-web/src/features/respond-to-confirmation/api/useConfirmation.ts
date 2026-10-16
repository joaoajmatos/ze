import type { WsOutboundFrame } from "@myguyze/ze-client";
import { useSendNotice } from "@/features/send-context-notice";
import { useWsStore, send } from "@/shared/api";
import { useMemo } from "react";
import { HELD_KEY, type PendingConfirm, usePendingConfirms } from "../model/pending-store";

const NONE: PendingConfirm[] = [];
const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";

export function useConfirmation(ephemeral: boolean, threadId: string) {
  const stored = usePendingConfirms((s) => s.byThread[threadId]);
  const held = usePendingConfirms((s) => s.byThread[HELD_KEY]);
  const pendingConfirms = useMemo(
    () => (ephemeral ? NONE : [...(held ?? NONE), ...(stored ?? NONE)]),
    [ephemeral, held, stored],
  );
  const setThreadThinking = useWsStore((s) => s.setThreadThinking);

  function respond(id: string, value: string, edits: Record<string, string> = {}) {
    const confirm = pendingConfirms.find((c) => c.id === id);
    if (!confirm || confirm.submitted) return;
    const isHeld = confirm.threadId === HELD_KEY;
    const sendThread = isHeld ? threadId : confirm.threadId;
    const checkpoint = value === "approve" || value === "deny";

    const sent = send(
      (checkpoint
        ? {
            type: "confirm",
            id: confirm.id,
            choice: value,
            thread_id: sendThread,
            ...(value === "approve" ? { edits } : {}),
          }
        : { type: "action", payload: value, thread_id: sendThread }) as WsOutboundFrame,
    );

    if (!sent) {
      useSendNotice.getState().showNotice(NOT_CONNECTED_NOTICE);
      return;
    }

    // Item cards wait for confirm_cancel or the next round; prompt and held cards close at once
    // (a held run resumes off-thread, so no frame on this thread would acknowledge it).
    if (confirm.items.length > 0 && !isHeld) usePendingConfirms.getState().markSubmitted(confirm.threadId, id);
    else usePendingConfirms.getState().remove(confirm.threadId, id);
    if (checkpoint && !isHeld) setThreadThinking(threadId, true);
  }

  function clear() {
    usePendingConfirms.getState().clear(threadId);
  }

  return { pendingConfirms, respond, clear };
}
