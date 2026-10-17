import type { WsScreenContext, WsScreenRef } from "@myguyze/ze-client";
import { create } from "zustand";

export interface OutboxItem {
  id: number;
  text: string;
  context: WsScreenContext;
}

/** The thing the person chose to chat about, until they remove it or the overlay closes. */
export interface ChatAboutSubject {
  ref: WsScreenRef;
  /** `chat_about` until the first message is sent from it, then `ask_bar`. */
  origin: "chat_about" | "ask_bar";
  suggestions: string[];
}

interface AskOverlayState {
  open: boolean;
  /** What the Ask bar input holds; `askAbout` fills it. */
  draft: string;
  /** Bumps when something asks the Ask bar to take focus. */
  focusTick: number;
  /** Context set by `askAbout` / `chatAbout`; merged over the route's until the overlay closes. */
  explicitContext: WsScreenContext | null;
  /** The subject chip and suggestions shown by the overlay and by the Ask composer. */
  about: ChatAboutSubject | null;
  /** Bumps to ask the shell to turn the orb toward `glanceTarget`. */
  glanceTick: number;
  glanceTarget: Element | null;
  /** The one message waiting to be sent on the overlay thread. */
  outbox: OutboxItem | null;
  /** Queue a message and open the overlay. False when an item is already waiting. */
  submit: (text: string, routeContext: WsScreenContext) => boolean;
  setDraft: (draft: string) => void;
  openWith: (prefill: string | null, context: WsScreenContext | null) => void;
  /** Start a chat about `ref`: the overlay opens (or, when `inPlace`, the Ask composer takes it). */
  startAbout: (about: ChatAboutSubject, options: { inPlace: boolean; element?: Element | null; glance: boolean }) => void;
  clearAbout: () => void;
  /** The overlay sent item `id`; drop it. The explicit context stays, but its origin is `ask_bar` now. */
  ack: (id: number) => void;
  /** The Ask composer sent a message about the subject. */
  aboutSent: () => void;
  close: () => void;
  reset: () => void;
}

let nextId = 1;

const INITIAL = { open: false, explicitContext: null, outbox: null, about: null } as const;

/** What the engine gets for a chat about `about`. */
export function aboutContext(about: ChatAboutSubject): WsScreenContext {
  return { origin: about.origin, subject: [about.ref] };
}

export const useAskOverlay = create<AskOverlayState>((set, get) => ({
  ...INITIAL,
  draft: "",
  focusTick: 0,
  glanceTick: 0,
  glanceTarget: null,
  submit: (text, routeContext) => {
    if (get().outbox) return false;
    const context = { ...routeContext, ...get().explicitContext } as WsScreenContext;
    set({ open: true, draft: "", outbox: { id: nextId++, text, context } });
    return true;
  },
  setDraft: (draft) => set({ draft }),
  openWith: (prefill, context) =>
    set((s) => ({ open: true, draft: prefill ?? s.draft, focusTick: s.focusTick + 1, explicitContext: context })),
  startAbout: (about, { inPlace, element, glance }) =>
    set((s) => ({
      about,
      explicitContext: inPlace ? s.explicitContext : aboutContext(about),
      open: inPlace ? s.open : true,
      focusTick: s.focusTick + 1,
      glanceTick: glance ? s.glanceTick + 1 : s.glanceTick,
      glanceTarget: glance ? (element ?? null) : s.glanceTarget,
    })),
  clearAbout: () => set({ about: null, explicitContext: null }),
  ack: (id) =>
    set((s) => {
      if (s.outbox?.id !== id) return s;
      const explicit = s.explicitContext?.origin === "chat_about" ? { ...s.explicitContext, origin: "ask_bar" as const } : s.explicitContext;
      return { outbox: null, explicitContext: explicit, about: s.about ? { ...s.about, origin: "ask_bar" } : null };
    }),
  aboutSent: () => set((s) => (s.about && s.about.origin !== "ask_bar" ? { about: { ...s.about, origin: "ask_bar" } } : s)),
  // An unsent message goes back into the bar rather than vanishing.
  close: () =>
    set((s) => ({ ...INITIAL, draft: s.outbox ? [s.outbox.text, s.draft].filter(Boolean).join(" ") : s.draft })),
  reset: () => set({ ...INITIAL, draft: "", focusTick: 0, glanceTick: 0, glanceTarget: null }),
}));

/** Open the overlay with the Ask bar prefilled (not sent) and the context a page knows best. */
export function askAbout({ text, context }: { text?: string; context: WsScreenContext }): void {
  useAskOverlay.getState().openWith(text ?? null, context);
}
