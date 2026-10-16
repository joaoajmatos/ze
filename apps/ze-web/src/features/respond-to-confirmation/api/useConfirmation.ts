import type { WsOutboundFrame } from "@myguyze/ze-client";
import { useSendNotice } from "@/features/send-context-notice";
import { useWsStore, send } from "@/shared/api";
import { usePendingConfirms } from "../model/pending-store";

const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";

export function useConfirmation(ephemeral: boolean, threadId: string) {
  const stored = usePendingConfirms((s) => s.byThread[threadId] ?? null);
  const pendingConfirm = ephemeral ? null : stored;
  const setThreadThinking = useWsStore((s) => s.setThreadThinking);

  function respond(value: string, edits: Record<string, string> = {}) {
    if (!pendingConfirm || pendingConfirm.submitted) return;
    const confirm = pendingConfirm;
    const checkpoint = value === "approve" || value === "deny";

    const sent = send(
      (checkpoint
        ? {
            type: "confirm",
            id: confirm.id,
            choice: value,
            thread_id: confirm.threadId,
            ...(value === "approve" ? { edits } : {}),
          }
        : { type: "action", payload: value, thread_id: confirm.threadId }) as WsOutboundFrame,
    );

    if (!sent) {
      useSendNotice.getState().showNotice(NOT_CONNECTED_NOTICE);
      return;
    }

    // Item cards wait for confirm_cancel or the next round; prompt cards close at once.
    if (confirm.items.length > 0) usePendingConfirms.getState().set({ ...confirm, submitted: true });
    else usePendingConfirms.getState().clear(confirm.threadId);
    if (checkpoint) setThreadThinking(threadId, true);
  }

  function clear() {
    usePendingConfirms.getState().clear(threadId);
  }

  return { pendingConfirm, respond, clear };
}
