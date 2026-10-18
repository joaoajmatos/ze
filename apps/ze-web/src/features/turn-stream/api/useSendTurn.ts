import type { WsScreenContext } from "@myguyze/ze-client";
import { useConversation } from "@/entities/conversation";
import { screenSnapshot } from "@/entities/screen-context";
import { useSession } from "@/entities/session";
import { send } from "@/shared/api";
import { useSendNotice } from "@/shared/lib";

const NOT_CONNECTED_NOTICE = "Not connected. Retry when Ze reconnects.";

export interface SendTurnOptions {
  /** What the caller knows best (a chat-about subject, a preset's `compose`). A context with `captured_at` is a finished snapshot and is sent as it was. */
  explicitContext?: WsScreenContext | null;
  workspacePlaced?: { path: string; size: number }[];
}

const isRunning = (threadId: string) => {
  const phase = useConversation.getState().byThread[threadId]?.turn.phase;
  return phase === "awaiting" || phase === "thinking" || phase === "speaking";
};

function dispatch(threadId: string, text: string, context: WsScreenContext, workspacePlaced: SendTurnOptions["workspacePlaced"], resend: boolean) {
  if (!send({ type: "message", text, thread_id: threadId, context })) {
    useSendNotice.getState().showNotice(NOT_CONNECTED_NOTICE);
    return false;
  }
  useConversation
    .getState()
    .apply({ type: "sent", threadId, text, context, workspacePlaced, resend }, { activeThreadId: useSession.getState().threadId });
  return true;
}

/** The one place a person's message leaves the client. */
export function sendTurn(threadId: string, text: string, { explicitContext, workspacePlaced }: SendTurnOptions = {}): boolean {
  const trimmed = text.trim();
  if (!trimmed || isRunning(threadId)) return false;
  const context: WsScreenContext = {
    ...(explicitContext?.captured_at ? {} : screenSnapshot()),
    ...explicitContext,
    ...(workspacePlaced?.length ? { workspace_placed: workspacePlaced } : {}),
  };
  return dispatch(threadId, trimmed, context, workspacePlaced, false);
}

/** Sends the last message again with what it was sent with; the original line stays. */
export function resendTurn(threadId: string): boolean {
  const last = useConversation.getState().byThread[threadId]?.turn.lastSent;
  if (!last || isRunning(threadId)) return false;
  return dispatch(threadId, last.text, last.context, last.workspacePlaced, true);
}

export function useSendTurn() {
  return { sendTurn, resendTurn };
}
