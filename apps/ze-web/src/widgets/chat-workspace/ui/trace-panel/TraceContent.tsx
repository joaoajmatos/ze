import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import {
  threadTraceBucket,
  useSessionTraces,
  useTraceSocket,
  useTraceStore,
} from "@/features/trace-state";
import { useMessageFeedbackQuery } from "@/entities/message-feedback";
import { useWsStore } from "@/shared/api";
import { FeedbackSection } from "./FeedbackSection";
import { TraceEmptyState } from "./TraceEmptyState";
import { TraceEntry } from "./TraceEntry";

const EMPTY_TRACE: Omit<WsTraceUpdateFrame, "type" | "message_id"> = {
  thread_id: "",
  agent: "",
  routing_method: "",
  confidence: 0,
  score_gap: 0,
  is_compound: false,
  subtasks: [],
  memory_chunks: [],
  tool_calls: [],
  total_duration_ms: 0,
  skills_used: [],
  conductor_hint: null,
  conductor_ledger: [],
  judgments: [],
};

interface TraceContentProps {
  threadId: string;
  assistantMessageIds: string[];
}

export function TraceContent({ threadId, assistantMessageIds }: TraceContentProps) {
  useTraceSocket();
  const hydrating = useSessionTraces(threadId, assistantMessageIds);

  const bucket = useTraceStore((s) => threadTraceBucket(s, threadId));
  const thinking = useWsStore((s) => s.thinkingThreads[threadId] ?? false);
  const traces = bucket.traces;
  const pending = bucket.pending || thinking;
  const pendingTrace = bucket.pendingTrace;
  const { byId: feedbackById } = useMessageFeedbackQuery(assistantMessageIds);
  const tracedIds = new Set(traces.map((t) => t.message_id));
  const untraced = assistantMessageIds.filter((id) => {
    const f = feedbackById.get(id);
    return f && !tracedIds.has(id) && (f.current || (f.history ?? []).length > 0);
  });
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (traces.length > 0 || pendingTrace) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [traces.length, pendingTrace]);

  const liveTrace: WsTraceUpdateFrame | null = pendingTrace
    ? { type: "trace_update", message_id: "", ...EMPTY_TRACE, thread_id: threadId, ...pendingTrace }
    : null;

  const showEmpty = traces.length === 0 && untraced.length === 0 && !pending && !liveTrace && !hydrating;

  return (
    <div className="text-xs h-full">
      {showEmpty ? (
        <TraceEmptyState />
      ) : (
        <div>
          {traces.map((trace, i) => (
            <TraceEntry
              key={trace.message_id}
              trace={trace}
              index={i}
              defaultOpen={i === traces.length - 1 && !liveTrace}
              feedback={feedbackById.get(trace.message_id)}
            />
          ))}
          {untraced.map((id) => (
            <div
              key={id}
              data-testid="untraced-feedback"
              className="border-b border-foreground/[0.06] last:border-b-0"
            >
              <p className="px-3 pt-2 text-[10px] text-smoke">
                Reply <span className="font-mono">{id.slice(0, 8)}</span> · no trace recorded
              </p>
              <FeedbackSection feedback={feedbackById.get(id)} />
            </div>
          ))}
          {liveTrace && (
            <TraceEntry
              trace={liveTrace}
              index={traces.length}
              defaultOpen={true}
              live={true}
            />
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {hydrating && traces.length === 0 && !liveTrace && (
        <div className="flex items-center gap-2 justify-center px-3 py-8 text-xs text-smoke">
          <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
          Loading traces…
        </div>
      )}

      {pending && !liveTrace && (
        <div className="sticky bottom-0 flex items-center gap-2 px-3 py-2 bg-background/60 border-t border-foreground/[0.06] text-xs text-smoke">
          <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
          Ze is thinking…
        </div>
      )}
    </div>
  );
}
