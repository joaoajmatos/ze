import type { WsConfirmAction, WsConfirmRequestFrame } from "@myguyze/ze-client";
import { create } from "zustand";
import type { ConfirmItem, ConfirmSource } from "./types";

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

/** Held writes belong to no thread; they sit under this key and show on every thread. */
export const HELD_KEY = "*";

interface PendingConfirmState {
  byThread: Record<string, PendingConfirm[]>;
  /** Adds or replaces by request id. An answered card of the same thread is dropped: the server moved on. */
  upsert: (pending: PendingConfirm) => void;
  markSubmitted: (threadId: string, id: string) => void;
  remove: (threadId: string, id: string) => void;
  /** Request ids are unique across threads, so a cancel never needs the thread. */
  cancel: (id: string) => void;
  /** The server acknowledged the answer by resuming the thread. */
  acknowledge: (threadId: string) => void;
  clear: (threadId: string) => void;
}

function without(byThread: Record<string, PendingConfirm[]>, threadId: string, keep: (p: PendingConfirm) => boolean) {
  const current = byThread[threadId];
  if (!current) return byThread;
  const next = current.filter(keep);
  if (next.length === current.length) return byThread;
  if (next.length === 0) {
    const { [threadId]: _gone, ...rest } = byThread;
    return rest;
  }
  return { ...byThread, [threadId]: next };
}

export const usePendingConfirms = create<PendingConfirmState>((set) => ({
  byThread: {},
  upsert: (pending) =>
    set((s) => {
      const open = (s.byThread[pending.threadId] ?? []).filter(
        (p) => p.id === pending.id || !p.submitted,
      );
      const exists = open.some((p) => p.id === pending.id);
      const next = exists ? open.map((p) => (p.id === pending.id ? pending : p)) : [...open, pending];
      return { byThread: { ...s.byThread, [pending.threadId]: next } };
    }),
  markSubmitted: (threadId, id) =>
    set((s) => ({
      byThread: {
        ...s.byThread,
        [threadId]: (s.byThread[threadId] ?? []).map((p) => (p.id === id ? { ...p, submitted: true } : p)),
      },
    })),
  remove: (threadId, id) => set((s) => ({ byThread: without(s.byThread, threadId, (p) => p.id !== id) })),
  cancel: (id) =>
    set((s) => {
      let byThread = s.byThread;
      for (const threadId of Object.keys(s.byThread)) {
        byThread = without(byThread, threadId, (p) => p.id !== id);
      }
      return byThread === s.byThread ? s : { byThread };
    }),
  acknowledge: (threadId) =>
    set((s) => ({ byThread: without(s.byThread, threadId, (p) => !p.submitted) })),
  clear: (threadId) => set((s) => ({ byThread: without(s.byThread, threadId, () => false) })),
}));

export function toPending(frame: WsConfirmRequestFrame, threadId: string): PendingConfirm {
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
