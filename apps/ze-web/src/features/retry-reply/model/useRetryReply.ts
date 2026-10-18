import type { WsOutboundFrame } from "@myguyze/ze-client";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useConversation, useThread } from "@/entities/conversation";
import { useSession } from "@/entities/session";
import { send } from "@/shared/api";
import { queryKeys } from "@/shared/lib";

const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";

interface UseRetryReplyOptions {
  threadId: string;
  onNotice: (text: string) => void;
}

/**
 * Sends a retry. The conversation store applies what comes back (a superseded reply, a rollback record, an
 * outcome); this hook only starts the retry and refreshes the feedback and trace queries when those change.
 */
export function useRetryReply({ threadId, onNotice }: UseRetryReplyOptions) {
  const queryClient = useQueryClient();
  const thread = useThread(threadId);
  const phase = thread.turn.phase;
  const running = phase === "awaiting" || phase === "thinking" || phase === "speaking";
  const pendingId = thread.turn.retryOf ?? null;
  const retrying = pendingId !== null && running;

  const changes = thread.messages.map((m) => `${m.id}:${m.replaced_by ?? ""}:${m.rollback?.state ?? ""}`).join("|") + `#${thread.lastOutcome?.kind ?? ""}`;
  const seen = useRef(changes);
  useEffect(() => {
    if (seen.current === changes) return;
    seen.current = changes;
    void queryClient.invalidateQueries({ queryKey: queryKeys.messageFeedbackAll });
    void queryClient.invalidateQueries({ queryKey: ["message-trace"] });
    void queryClient.invalidateQueries({ queryKey: ["message-traces"] });
  }, [changes, queryClient]);

  function retry(messageId: string, confirmedPlan?: string[]): boolean {
    if (running) return false;
    const frame: Extract<WsOutboundFrame, { type: "retry" }> = {
      type: "retry",
      message_id: messageId,
      thread_id: threadId,
      ...(confirmedPlan && confirmedPlan.length > 0 ? { confirmed_plan: confirmedPlan } : {}),
    };
    if (!send(frame)) {
      onNotice(NOT_CONNECTED_NOTICE);
      return false;
    }
    useConversation.getState().apply({ type: "retry_sent", threadId, messageId }, { activeThreadId: useSession.getState().threadId });
    return true;
  }

  return { retry, retrying, retryingId: retrying ? pendingId : null, outcome: thread.lastOutcome };
}
