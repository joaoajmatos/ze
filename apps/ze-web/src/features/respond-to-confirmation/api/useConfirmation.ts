import type { WsConfirmAction, WsConfirmRequestFrame, WsOutboundFrame } from "@myguyze/ze-client";
import { useState } from "react";
import { useSendNotice } from "@/features/send-context-notice";
import { useFrame, useWsStore, send } from "@/shared/api";
import type { ConfirmItem, ConfirmSource } from "../model/types";

export interface PendingConfirm {
  id: string;
  threadId: string;
  kind: WsConfirmRequestFrame["kind"];
  round: number;
  title: string;
  items: ConfirmItem[];
  source: ConfirmSource | null;
  expiresAt: string | null;
  actions: WsConfirmAction[];
  submitted: boolean;
}

function toPending(frame: WsConfirmRequestFrame, threadId: string): PendingConfirm {
  return {
    id: frame.id,
    threadId,
    kind: frame.kind,
    round: frame.round ?? 1,
    title: frame.title,
    items: frame.items,
    source: frame.source ?? null,
    expiresAt: frame.expires_at ?? null,
    actions: frame.actions,
    submitted: false,
  };
}

const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";

export function useConfirmation(active: boolean, ephemeral: boolean, threadId: string) {
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const setThreadThinking = useWsStore((s) => s.setThreadThinking);
  const setThreadAttention = useWsStore((s) => s.setThreadAttention);

  useFrame("confirm_request", (frame) => {
    if (ephemeral) return;
    const frameThread = frame.thread_id ?? threadId;
    if (frameThread !== threadId) {
      setThreadAttention(frameThread, true);
      return;
    }
    if (!active) return;
    setThreadThinking(threadId, false);
    setPendingConfirm(toPending(frame, threadId));
  });

  useFrame("confirm_cancel", (frame) => {
    const frameThread = frame.thread_id ?? threadId;
    if (frameThread !== threadId) return;
    if (!active || ephemeral) return;
    setPendingConfirm((current) => (current && current.id === frame.id ? null : current));
  });

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
    setPendingConfirm(confirm.items.length > 0 ? { ...confirm, submitted: true } : null);
    if (checkpoint) setThreadThinking(threadId, true);
  }

  function clear() {
    setPendingConfirm(null);
  }

  return { pendingConfirm, respond, clear };
}
