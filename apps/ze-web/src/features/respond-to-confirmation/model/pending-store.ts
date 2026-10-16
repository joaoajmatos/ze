import { create } from "zustand";
import type { WsConfirmAction, WsConfirmRequestFrame } from "@myguyze/ze-client";
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

interface PendingConfirmState {
  byThread: Record<string, PendingConfirm>;
  set: (pending: PendingConfirm) => void;
  cancel: (threadId: string, id: string) => void;
  clear: (threadId: string) => void;
}

export const usePendingConfirms = create<PendingConfirmState>((set) => ({
  byThread: {},
  set: (pending) => set((s) => ({ byThread: { ...s.byThread, [pending.threadId]: pending } })),
  cancel: (threadId, id) =>
    set((s) => {
      if (s.byThread[threadId]?.id !== id) return s;
      const { [threadId]: _gone, ...rest } = s.byThread;
      return { byThread: rest };
    }),
  clear: (threadId) =>
    set((s) => {
      if (!(threadId in s.byThread)) return s;
      const { [threadId]: _gone, ...rest } = s.byThread;
      return { byThread: rest };
    }),
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
