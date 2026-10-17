import type { WsCanvasRef, WsScreenRef } from "@myguyze/ze-client";
import { create } from "zustand";

/** What one page or widget knows is on screen: refs the engine resolves from its own records. */
export interface ScreenPublication {
  subject?: WsScreenRef[];
  selection?: WsScreenRef[];
  visible?: WsScreenRef[];
  focused_module?: string;
  canvas?: WsCanvasRef[];
}

interface ScreenContextState {
  /** Keyed by publisher token; a Map keeps mount order, which sets priority when caps bite. */
  publications: Map<string, ScreenPublication>;
  publish: (token: string, publication: ScreenPublication) => void;
  remove: (token: string) => void;
  reset: () => void;
}

export const useScreenContextStore = create<ScreenContextState>((set) => ({
  publications: new Map(),
  publish: (token, publication) =>
    set((s) => {
      const next = new Map(s.publications);
      next.set(token, publication);
      return { publications: next };
    }),
  remove: (token) =>
    set((s) => {
      if (!s.publications.has(token)) return s;
      const next = new Map(s.publications);
      next.delete(token);
      return { publications: next };
    }),
  reset: () => set({ publications: new Map() }),
}));
