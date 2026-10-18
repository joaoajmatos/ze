import type { WsOutboundFrame } from "@myguyze/ze-client";
import { useMemo } from "react";
import { useConversation } from "@/entities/conversation";
import { useSession } from "@/entities/session";
import { send } from "@/shared/api";
import { useSendNotice } from "@/shared/lib";
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
    // The turn goes on after an approve or deny; the conversation store restarts its clock and the
    // shell handler raises the thinking flags from that.
    if (checkpoint && !isHeld) {
      useConversation.getState().apply({ type: "resumed", threadId }, { activeThreadId: useSession.getState().threadId });
    }
  }

  function clear() {
    usePendingConfirms.getState().clear(threadId);
  }

  return { pendingConfirms, respond, clear };
}
