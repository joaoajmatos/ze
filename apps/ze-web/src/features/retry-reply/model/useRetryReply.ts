import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { send, useWsStore } from "@/shared/api";
import { queryKeys } from "@/shared/lib";
import {
  useRetryFrame,
  type MessageSupersededFrame,
  type RetryErrorFrame,
  type RetryOutboundFrame,
} from "./frames";

export const RETRY_FAILED_NOTICE = "Retry failed. The original reply is unchanged.";
const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";

interface UseRetryReplyOptions {
  threadId: string;
  /** Called when the server replaced `messageId` with `replacedBy`. */
  onSuperseded: (messageId: string, replacedBy: string) => void;
  onNotice: (text: string) => void;
}

export function useRetryReply({ threadId, onSuperseded, onNotice }: UseRetryReplyOptions) {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const isThinking = useWsStore((s) => s.thinkingThreads[threadId] ?? false);
  const setThreadThinking = useWsStore((s) => s.setThreadThinking);
  // The shared thinking flag also covers ordinary turns and drops on disconnect.
  const retrying = pendingId !== null && isThinking;

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.messageFeedbackAll });
    void queryClient.invalidateQueries({ queryKey: ["message-trace"] });
    void queryClient.invalidateQueries({ queryKey: ["message-traces"] });
  }

  function retry(messageId: string): boolean {
    if (isThinking) return false;
    const frame: RetryOutboundFrame = { type: "retry", message_id: messageId, thread_id: threadId };
    if (!send(frame as never)) {
      onNotice(NOT_CONNECTED_NOTICE);
      return false;
    }
    setPendingId(messageId);
    setThreadThinking(threadId, true);
    return true;
  }

  useRetryFrame<MessageSupersededFrame>("message_superseded", (frame) => {
    if (frame.thread_id !== threadId) return;
    setPendingId(null);
    onSuperseded(frame.message_id, frame.replaced_by);
    refresh();
  });

  useRetryFrame<RetryErrorFrame>("error", (frame) => {
    if (!pendingId || (frame.thread_id && frame.thread_id !== threadId)) return;
    if (frame.code === "retry_unavailable") {
      onNotice(frame.reason_text ?? "Ze cannot retry this reply.");
      refresh();
    } else if (frame.code === "busy") {
      onNotice(frame.detail);
    } else {
      onNotice(RETRY_FAILED_NOTICE);
    }
    setPendingId(null);
  });

  return { retry, retrying, retryingId: retrying ? pendingId : null };
}
