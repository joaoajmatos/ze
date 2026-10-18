import { create } from "zustand";
import {
  emptyThread,
  reduce,
  type ConversationEvent,
  type ConversationState,
  type ReduceContext,
  type ThreadState,
} from "./reducer";

interface ConversationStore extends ConversationState {
  /** `ctx.activeThreadId` is the thread on screen; the caller reads it from the session store. */
  apply: (event: ConversationEvent, ctx: ReduceContext) => void;
}

export const useConversation = create<ConversationStore>((set) => ({
  byThread: {},
  apply: (event, ctx) => set((s) => reduce({ byThread: s.byThread }, event, Date.now(), ctx)),
}));

const EMPTY = emptyThread();

export function useThread(threadId: string): ThreadState {
  return useConversation((s) => s.byThread[threadId] ?? EMPTY);
}

export function useTurn(threadId: string) {
  return useConversation((s) => (s.byThread[threadId] ?? EMPTY).turn);
}

/** Latest assistant reply that no retry replaced. */
export function latestAssistant(thread: ThreadState) {
  return [...thread.messages].reverse().find((m) => m.role === "assistant" && !m.replaced_by) ?? null;
}
