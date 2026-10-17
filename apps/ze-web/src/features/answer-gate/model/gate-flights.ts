import { create } from "zustand";

export interface Flight {
  kind: "decide" | "redirect";
  threadId: string;
  sentAt: number;
  /** Stuck-goal answers end with a timeout line when nothing settles them; gate answers wait for the goals data. */
  timeout?: boolean;
}

interface GateFlightState {
  /** Answers sent and not yet confirmed by the goals data (or, for Redirect, by the server's first reply). */
  flights: Record<string, Flight>;
  /** Redirect was accepted; the next message on the thread is the user's instruction. */
  awaiting: Record<string, true>;
  errors: Record<string, string>;
}

export const useGateFlights = create<GateFlightState>(() => ({ flights: {}, awaiting: {}, errors: {} }));

export function without<T>(rec: Record<string, T>, id: string): Record<string, T> {
  if (!(id in rec)) return rec;
  const rest = { ...rec };
  delete rest[id];
  return rest;
}
