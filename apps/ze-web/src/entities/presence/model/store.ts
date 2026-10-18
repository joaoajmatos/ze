import { create } from "zustand";
import { INITIAL_PRESENCE, nextPresence, type PresenceEvent, type PresenceState } from "./presence";

interface PresenceStore {
  presence: PresenceState;
  dispatch: (event: PresenceEvent) => void;
  reset: () => void;
}

export const usePresenceStore = create<PresenceStore>((set) => ({
  presence: INITIAL_PRESENCE,
  dispatch: (event) => set((s) => ({ presence: nextPresence(s.presence, event, Date.now()) })),
  reset: () => set({ presence: INITIAL_PRESENCE }),
}));

/** Dispatch presence events from outside React (the Ask bar, world signals). */
export const presenceActions = {
  askFocus: () => usePresenceStore.getState().dispatch({ type: "ask_focus" }),
  askBlur: () => usePresenceStore.getState().dispatch({ type: "ask_blur" }),
  askText: (nonEmpty: boolean) => usePresenceStore.getState().dispatch({ type: "ask_text", nonEmpty }),
  voice: (state: "none" | "recording" | "transcribing") =>
    usePresenceStore.getState().dispatch({ type: state === "recording" ? "voice_recording" : state === "transcribing" ? "voice_transcribing" : "voice_idle" }),
  setWorldSignal: (orb: "attention" | "acting" | "assembling" | null) =>
    usePresenceStore.getState().dispatch({ type: "set_world_signal", orb }),
};
