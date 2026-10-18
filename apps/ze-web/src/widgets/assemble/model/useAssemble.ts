import { useMemo } from "react";
import { threadTraceBucket, useSessionTraces, useTraceStore } from "@/features/trace-state";
import { useThread, type ThreadState } from "@/entities/conversation";
import { useMessageFeedbackQuery } from "@/entities/message-feedback";
import { groupExchanges, type Exchange } from "../lib/exchanges";

export interface Assemble {
  thread: ThreadState;
  exchanges: Exchange[];
  assistantIds: string[];
  /** The latest reply a retry did not replace. */
  latestId: string | null;
  feedbackById: ReturnType<typeof useMessageFeedbackQuery>["byId"];
  traceBucket: ReturnType<typeof threadTraceBucket>;
}

/** One thread joined from the conversation store, the trace store and reply feedback. */
export function useAssemble(threadId: string, hiddenMessageIds?: ReadonlySet<string> | null): Assemble {
  const thread = useThread(threadId);
  const exchanges = useMemo(
    () => groupExchanges(hiddenMessageIds ? thread.messages.filter((m) => !hiddenMessageIds.has(m.id)) : thread.messages),
    [thread.messages, hiddenMessageIds],
  );
  const assistantIds = useMemo(
    () => thread.messages.filter((m) => m.role === "assistant" && m.id).map((m) => String(m.id)),
    [thread.messages],
  );
  const latestId = useMemo(() => exchanges.flatMap((e) => e.replies).at(-1)?.id ?? null, [exchanges]);
  useSessionTraces(threadId, assistantIds);
  const { byId: feedbackById } = useMessageFeedbackQuery(assistantIds);
  const traceBucket = useTraceStore((s) => threadTraceBucket(s, threadId));
  return { thread, exchanges, assistantIds, latestId, feedbackById, traceBucket };
}
