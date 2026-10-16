import type {
  WsConfirmAction,
  WsConfirmItem,
  WsConfirmSource,
  WsOutboundFrame,
} from "@myguyze/ze-client";
import { useState } from "react";
import { useSendNotice } from "@/features/send-context-notice";
import { useFrame, useWsStore, send } from "@/shared/api";

export interface PendingConfirm {
  id: string;
  threadId: string;
  kind: "write" | "budget" | "held";
  round: number;
  title: string;
  items: WsConfirmItem[];
  source: WsConfirmSource | null;
  expiresAt: string | null;
  actions: WsConfirmAction[];
  submitted: boolean;
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
    setPendingConfirm({
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
    });
  });

  useFrame("confirm_cancel", (frame) => {
    const frameThread = frame.thread_id ?? threadId;
    if (frameThread !== threadId) return;
    if (!active || ephemeral) return;
    setPendingConfirm((current) => (current && current.id === frame.id ? null : current));
  });

  function respond(choice: "approve" | "deny", edits: Record<string, string> = {}) {
    if (!pendingConfirm || pendingConfirm.submitted) return;
    const confirm = pendingConfirm;
    setPendingConfirm({ ...confirm, submitted: true });

    const sent = send({
      type: "confirm",
      id: confirm.id,
      choice,
      thread_id: confirm.threadId,
      ...(choice === "approve" ? { edits } : {}),
    } as WsOutboundFrame);

    if (!sent) {
      setPendingConfirm(confirm);
      useSendNotice.getState().showNotice(NOT_CONNECTED_NOTICE);
      return;
    }

    setThreadThinking(threadId, true);
  }

  function clear() {
    setPendingConfirm(null);
  }

  return { pendingConfirm, respond, clear };
}
