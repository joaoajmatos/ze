import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { create } from "zustand";

export interface ThreadTraceBucket {
  traces: WsTraceUpdateFrame[];
  pending: boolean;
  pendingTrace: Partial<WsTraceUpdateFrame> | null;
  hydrating: boolean;
}

export function emptyThreadTrace(): ThreadTraceBucket {
  return { traces: [], pending: false, pendingTrace: null, hydrating: false };
}

export function tracesForThread(
  state: Pick<TraceState, "byThread">,
  threadId: string,
): WsTraceUpdateFrame[] {
  return state.byThread[threadId]?.traces ?? [];
}

export function threadTraceBucket(
  state: Pick<TraceState, "byThread">,
  threadId: string,
): ThreadTraceBucket {
  return state.byThread[threadId] ?? emptyThreadTrace();
}

function namedThreadId(value: unknown): string | null {
  if (typeof value !== "string" || value.length === 0) return null;
  return value;
}

function dedupeAppend(traces: WsTraceUpdateFrame[], trace: WsTraceUpdateFrame): WsTraceUpdateFrame[] {
  const without = traces.filter((t) => t.message_id !== trace.message_id);
  return [...without, trace];
}

function mergeOrdered(
  existing: WsTraceUpdateFrame[],
  incoming: WsTraceUpdateFrame[],
  orderedIds: string[],
): WsTraceUpdateFrame[] {
  const byId = new Map(existing.map((t) => [t.message_id, t]));
  for (const trace of incoming) {
    byId.set(trace.message_id, trace);
  }
  return orderedIds
    .map((id) => byId.get(id))
    .filter((t): t is WsTraceUpdateFrame => t !== undefined);
}

function tracesEqual(a: WsTraceUpdateFrame[], b: WsTraceUpdateFrame[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((t, i) => t.message_id === b[i]?.message_id);
}

function updateThread(
  byThread: Record<string, ThreadTraceBucket>,
  threadId: string,
  updater: (bucket: ThreadTraceBucket) => ThreadTraceBucket,
): Record<string, ThreadTraceBucket> {
  const current = byThread[threadId] ?? emptyThreadTrace();
  return { ...byThread, [threadId]: updater(current) };
}

interface TraceState {
  byThread: Record<string, ThreadTraceBucket>;
  appendTrace: (t: WsTraceUpdateFrame) => void;
  clearTraces: (threadId: string) => void;
  setPending: (threadId: string, v: boolean) => void;
  setHydrating: (threadId: string, v: boolean) => void;
  mergeTraces: (threadId: string, incoming: WsTraceUpdateFrame[], orderedIds: string[]) => void;
  mergePartialTrace: (fields: Partial<WsTraceUpdateFrame>) => void;
  commitPendingTrace: (final: WsTraceUpdateFrame) => void;
}

export const useTraceStore = create<TraceState>()((set) => ({
  byThread: {},
  appendTrace: (t) =>
    set((s) => {
      const threadId = namedThreadId(t.thread_id);
      if (!threadId) return s;
      return {
        byThread: updateThread(s.byThread, threadId, (bucket) => ({
          ...bucket,
          traces: dedupeAppend(bucket.traces, t),
          pending: false,
        })),
      };
    }),
  clearTraces: (threadId) =>
    set((s) => ({
      byThread: updateThread(s.byThread, threadId, () => emptyThreadTrace()),
    })),
  setPending: (threadId, v) =>
    set((s) => ({
      byThread: updateThread(s.byThread, threadId, (bucket) =>
        bucket.pending === v ? bucket : { ...bucket, pending: v },
      ),
    })),
  setHydrating: (threadId, v) =>
    set((s) => ({
      byThread: updateThread(s.byThread, threadId, (bucket) =>
        bucket.hydrating === v ? bucket : { ...bucket, hydrating: v },
      ),
    })),
  mergeTraces: (threadId, incoming, orderedIds) =>
    set((s) => {
      const current = s.byThread[threadId] ?? emptyThreadTrace();
      const merged = mergeOrdered(current.traces, incoming, orderedIds);
      if (tracesEqual(merged, current.traces) && !current.hydrating) return s;
      return {
        byThread: updateThread(s.byThread, threadId, (bucket) => ({
          ...bucket,
          traces: merged,
          hydrating: false,
        })),
      };
    }),
  mergePartialTrace: (fields) =>
    set((s) => {
      const threadId = namedThreadId(fields.thread_id);
      if (!threadId) return s;
      return {
        byThread: updateThread(s.byThread, threadId, (bucket) => {
          const base = bucket.pendingTrace ?? {};
          const { memory_chunks: newChunks = [], tool_calls: newCalls = [], ...rest } = fields;
          return {
            ...bucket,
            pendingTrace: {
              ...base,
              ...rest,
              memory_chunks: [...(base.memory_chunks ?? []), ...newChunks],
              tool_calls: [...(base.tool_calls ?? []), ...newCalls],
            },
          };
        }),
      };
    }),
  commitPendingTrace: (final) =>
    set((s) => {
      const threadId = namedThreadId(final.thread_id);
      if (!threadId) return s;
      return {
        byThread: updateThread(s.byThread, threadId, (bucket) => ({
          ...bucket,
          traces: dedupeAppend(bucket.traces, final),
          pendingTrace: null,
          pending: false,
        })),
      };
    }),
}));
