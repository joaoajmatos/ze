import { useSession } from "@/entities/session";
import { useFrame } from "@/shared/api";
import { useGateFlights, without } from "../model/gate-flights";

/** An `error` frame this soon after the send is taken to be the server's answer to it (the server sends no ack). */
export const ERROR_WINDOW_MS = 15_000;

/**
 * Listens for the server's replies to gate answers. Mounted once in the shell, so a reply that arrives
 * while World is closed still settles the flight. One error frame settles the oldest answer still waiting.
 */
export function AnswerGateFrameHandler() {
  const threadId = useSession((s) => s.threadId);

  useFrame("message", (f) => {
    if (f.message.thread_id !== threadId) return;
    useGateFlights.setState((s) => {
      const redirecting = Object.entries(s.flights).filter(([, fl]) => fl.kind === "redirect" && fl.threadId === threadId);
      if (redirecting.length === 0) return s;
      let flightsNext = s.flights;
      let awaitingNext = s.awaiting;
      for (const [id] of redirecting) {
        flightsNext = without(flightsNext, id);
        awaitingNext = { ...awaitingNext, [id]: true };
      }
      return { ...s, flights: flightsNext, awaiting: awaitingNext };
    });
  });

  useFrame("error", (f) => {
    if (f.thread_id !== threadId) return;
    const now = Date.now();
    useGateFlights.setState((s) => {
      const waiting = Object.entries(s.flights)
        .filter(([, fl]) => fl.threadId === threadId && (fl.kind === "redirect" || now - fl.sentAt <= ERROR_WINDOW_MS))
        .sort((a, b) => a[1].sentAt - b[1].sentAt)[0];
      if (!waiting) return s;
      const [id] = waiting;
      return { ...s, flights: without(s.flights, id), errors: { ...s.errors, [id]: f.detail } };
    });
  });

  return null;
}
