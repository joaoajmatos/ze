import type { OrbState } from "@/shared/ui/hud/presence/types";

export const DONE_BLOOM_MS = 1000;

export type PresenceEvent =
  | { type: "ws_open" }
  | { type: "ws_closed" }
  | { type: "ask_focus" }
  | { type: "ask_blur" }
  | { type: "ask_text"; nonEmpty: boolean }
  | { type: "turn_thinking"; text?: string | null }
  | { type: "turn_token" }
  | { type: "turn_message" }
  | { type: "turn_error" }
  | { type: "turn_reset" }
  | { type: "settle" }
  | { type: "set_world_signal"; orb: "attention" | "acting" | "assembling" | null };

export interface PresenceState {
  orb: OrbState;
  phrase: string;
  offline: boolean;
  turn: "none" | "thinking" | "speaking";
  turnPhrase: string | null;
  askFocused: boolean;
  askHasText: boolean;
  worldSignal: "attention" | "acting" | "assembling" | null;
  doneUntil: number | null;
}

const WORLD_PHRASES = {
  attention: "something needs you",
  acting: "working",
  assembling: "assembling the answer",
} as const;

function derive(s: Omit<PresenceState, "orb" | "phrase">, now: number): Pick<PresenceState, "orb" | "phrase"> {
  if (s.offline) return { orb: "error", phrase: "Offline" };
  if (s.doneUntil !== null && now < s.doneUntil) return { orb: "done", phrase: "done" };
  if (s.turn === "thinking") return { orb: "thinking", phrase: s.turnPhrase ?? "thinking" };
  if (s.turn === "speaking") return { orb: "speaking", phrase: "speaking" };
  if (s.askFocused && s.askHasText) return { orb: "listening", phrase: "listening" };
  if (s.worldSignal) return { orb: s.worldSignal, phrase: WORLD_PHRASES[s.worldSignal] };
  return { orb: "idle", phrase: "ready" };
}

const BASE: Omit<PresenceState, "orb" | "phrase"> = {
  offline: true,
  turn: "none",
  turnPhrase: null,
  askFocused: false,
  askHasText: false,
  worldSignal: null,
  doneUntil: null,
};

function baseOf(s: PresenceState): Omit<PresenceState, "orb" | "phrase"> {
  return {
    offline: s.offline,
    turn: s.turn,
    turnPhrase: s.turnPhrase,
    askFocused: s.askFocused,
    askHasText: s.askHasText,
    worldSignal: s.worldSignal,
    doneUntil: s.doneUntil,
  };
}

export const INITIAL_PRESENCE: PresenceState = { ...BASE, ...derive(BASE, 0) };

/** Pure: the orb state and phrase follow only real signals. `now` is the caller's clock. */
export function nextPresence(state: PresenceState, event: PresenceEvent, now: number): PresenceState {
  const base = baseOf(state);
  let next = base;
  switch (event.type) {
    case "ws_open":
      next = { ...base, offline: false };
      break;
    case "ws_closed":
      // In-flight turns are unobservable once the socket is gone.
      next = { ...base, offline: true, turn: "none", turnPhrase: null, doneUntil: null };
      break;
    case "ask_focus":
      next = { ...base, askFocused: true };
      break;
    case "ask_blur":
      next = { ...base, askFocused: false };
      break;
    case "ask_text":
      next = { ...base, askHasText: event.nonEmpty };
      break;
    case "turn_thinking":
      next = { ...base, turn: "thinking", turnPhrase: event.text || null, doneUntil: null };
      break;
    case "turn_token":
      next = { ...base, turn: "speaking", turnPhrase: null, doneUntil: null };
      break;
    case "turn_message":
      if (base.turn === "none") return state;
      next = { ...base, turn: "none", turnPhrase: null, doneUntil: now + DONE_BLOOM_MS };
      break;
    case "turn_error":
    case "turn_reset":
      next = { ...base, turn: "none", turnPhrase: null, doneUntil: null };
      break;
    case "settle":
      if (base.doneUntil === null || now < base.doneUntil) return state;
      next = { ...base, doneUntil: null };
      break;
    case "set_world_signal":
      next = { ...base, worldSignal: event.orb };
      break;
  }
  return { ...next, ...derive(next, now) };
}
