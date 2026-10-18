import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { create } from "zustand";

export interface ThreadTraceBucket {
  traces: WsTraceUpdateFrame[];
  pending: boolean;
  pendingTrace: Partial<WsTraceUpdateFrame> | null;
  hydrating: boolean;
  /** Client arrival time (ms) of each stage of the turn in flight: route, screen, memory, tier, `tool:<position>`. */
  pendingArrivals: Record<string, number>;
  /** The same stamps, kept for a committed reply. A trace hydrated from history has none. */
  arrivalsByMessage: Record<string, Record<string, number>>;
  /** When the turn in flight started (a send or a retry); the zero of its stage offsets. */
  pendingSentAt: number | null;
  /** The same zero, kept for a committed reply. */
  sentAtByMessage: Record<string, number>;
}

function emptyThreadTrace(): ThreadTraceBucket {
  return { traces: [], pending: false, pendingTrace: null, hydrating: false, pendingArrivals: {}, arrivalsByMessage: {}, pendingSentAt: null, sentAtByMessage: {} };
}

/** The stages a partial frame carries, by its fields. */
function stagesIn(fields: Partial<WsTraceUpdateFrame>, toolsSoFar: number): string[] {
  const stages: string[] = [];
  if (fields.agent) stages.push("route");
  if (fields.screen) stages.push("screen");
  if ((fields.memory_chunks?.length ?? 0) > 0) stages.push("memory");
  if (fields.tier) stages.push("tier");
  // The wire has no call index on a partial; the list position is the order the calls ended in.
  (fields.tool_calls ?? []).forEach((_, i) => stages.push(`tool:${toolsSoFar + i}`));
  return stages;
}

const EMPTY_BUCKET: ThreadTraceBucket = Object.freeze(emptyThreadTrace());

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
  // One shared empty bucket: a selector must return a stable value or React loops.
  return state.byThread[threadId] ?? EMPTY_BUCKET;
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
  /** A new turn starts: whatever a refused or failed turn left pending is dropped. */
  resetPending: (threadId: string) => void;
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
          const now = Date.now();
          const arrivals = { ...bucket.pendingArrivals };
          for (const stage of stagesIn(fields, base.tool_calls?.length ?? 0)) if (!(stage in arrivals)) arrivals[stage] = now;
          return {
            ...bucket,
            pendingArrivals: arrivals,
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
          pendingArrivals: {},
          pendingSentAt: null,
          sentAtByMessage:
            bucket.pendingSentAt !== null
              ? { ...bucket.sentAtByMessage, [final.message_id]: bucket.pendingSentAt }
              : bucket.sentAtByMessage,
          arrivalsByMessage: Object.keys(bucket.pendingArrivals).length
            ? { ...bucket.arrivalsByMessage, [final.message_id]: bucket.pendingArrivals }
            : bucket.arrivalsByMessage,
        })),
      };
    }),
  resetPending: (threadId) =>
    set((s) => ({
      byThread: updateThread(s.byThread, threadId, (bucket) => ({
        ...bucket,
        pendingTrace: null,
        pendingArrivals: {},
        pendingSentAt: Date.now(),
      })),
    })),
}));
