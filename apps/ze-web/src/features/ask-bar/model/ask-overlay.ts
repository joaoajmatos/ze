import type { WsScreenContext } from "@myguyze/ze-client";
import { create } from "zustand";

export interface OutboxItem {
  id: number;
  text: string;
  context: WsScreenContext;
}

interface AskOverlayState {
  open: boolean;
  /** What the Ask bar input holds; `askAbout` fills it. */
  draft: string;
  /** Bumps when something asks the Ask bar to take focus. */
  focusTick: number;
  /** Context set by `askAbout`; merged over the route's until sent or closed. */
  explicitContext: WsScreenContext | null;
  /** The one message waiting to be sent on the overlay thread. */
  outbox: OutboxItem | null;
  /** Queue a message and open the overlay. False when an item is already waiting. */
  submit: (text: string, routeContext: WsScreenContext) => boolean;
  setDraft: (draft: string) => void;
  openWith: (prefill: string | null, context: WsScreenContext | null) => void;
  /** The overlay sent item `id`; drop it and the explicit context. */
  ack: (id: number) => void;
  close: () => void;
  reset: () => void;
}

let nextId = 1;

const INITIAL = { open: false, explicitContext: null, outbox: null } as const;

export const useAskOverlay = create<AskOverlayState>((set, get) => ({
  ...INITIAL,
  draft: "",
  focusTick: 0,
  submit: (text, routeContext) => {
    if (get().outbox) return false;
    const context = { ...routeContext, ...get().explicitContext } as WsScreenContext;
    set({ open: true, draft: "", outbox: { id: nextId++, text, context } });
    return true;
  },
  setDraft: (draft) => set({ draft }),
  openWith: (prefill, context) =>
    set((s) => ({ open: true, draft: prefill ?? s.draft, focusTick: s.focusTick + 1, explicitContext: context })),
  ack: (id) => set((s) => (s.outbox?.id === id ? { outbox: null, explicitContext: null } : s)),
  close: () => set({ ...INITIAL }),
  reset: () => set({ ...INITIAL, draft: "", focusTick: 0 }),
}));

/** Open the overlay with the Ask bar prefilled (not sent) and the context a page knows best. */
export function askAbout({ text, context }: { text?: string; context: WsScreenContext }): void {
  useAskOverlay.getState().openWith(text ?? null, context);
}
