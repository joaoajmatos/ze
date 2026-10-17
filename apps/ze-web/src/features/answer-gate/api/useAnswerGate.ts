import { useEffect } from "react";
import { useSession } from "@/entities/session";
import { send, useWsStore } from "@/shared/api";
import { useGateFlights, without } from "../model/gate-flights";

export type GateState = "idle" | "in_flight" | "awaiting_instructions";

/**
 * Answer a goal gate. Gates have no REST route: the server reads an `action` frame on the session thread,
 * posts its reply into that thread and sends `refresh` (screen `goals`). `answer` is the one sender; another
 * payload family (such as `goal_stuck`) joins by passing its own prefix.
 */
export function useAnswerGate(openGateIds: readonly string[]) {
  const threadId = useSession((s) => s.threadId);
  const connected = useWsStore((s) => s.isConnected);
  const flights = useGateFlights((s) => s.flights);
  const awaiting = useGateFlights((s) => s.awaiting);
  const errors = useGateFlights((s) => s.errors);
  const openKey = openGateIds.join("|");

  // A decided gate is done when the goals data stops listing it.
  useEffect(() => {
    const open = new Set(openKey ? openKey.split("|") : []);
    useGateFlights.setState((s) => {
      const gone = [...Object.keys(s.flights), ...Object.keys(s.awaiting)].filter((id) => !open.has(id));
      if (gone.length === 0) return s;
      let next = s;
      for (const id of gone) next = { ...next, flights: without(next.flights, id), awaiting: without(next.awaiting, id) };
      return next;
    });
  }, [openKey]);

  function answer(family: string, action: string, id: string, kind: "decide" | "redirect" = "decide"): boolean {
    if (useGateFlights.getState().flights[id]) return false;
    const sent = send({ type: "action", payload: `${family}:${action}:${id}`, thread_id: threadId });
    if (!sent) return false;
    useGateFlights.setState((s) => ({
      flights: { ...s.flights, [id]: { kind, threadId, sentAt: Date.now() } },
      awaiting: kind === "decide" ? without(s.awaiting, id) : s.awaiting,
      errors: without(s.errors, id),
    }));
    return true;
  }

  function stateOf(id: string): GateState {
    if (flights[id]) return "in_flight";
    if (awaiting[id]) return "awaiting_instructions";
    return "idle";
  }

  return {
    offline: !connected,
    answer,
    proceed: (gateId: string) => answer("goal", "approve", gateId),
    stop: (gateId: string) => answer("goal", "stop", gateId),
    redirect: (gateId: string) => answer("goal", "redirect", gateId, "redirect"),
    stateOf,
    errorOf: (gateId: string): string | null => errors[gateId] ?? null,
  };
}
