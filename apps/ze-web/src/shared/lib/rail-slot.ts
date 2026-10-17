import { create } from "zustand";

interface RailSlotState {
  /** The element under Presence in the shell's left rail, where a place may put its own modules. */
  element: HTMLElement | null;
  setElement: (element: HTMLElement | null) => void;
}

export const useRailSlot = create<RailSlotState>((set) => ({
  element: null,
  setElement: (element) => set({ element }),
}));
