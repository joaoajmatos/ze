import { useEffect, useRef } from "react";
import { useConversation } from "@/entities/conversation";
import { useSession } from "@/entities/session";
import { useGateFlights, without } from "../model/gate-flights";

/** An `error` this soon after the send is taken to be the server's answer to it (the server sends no ack). */
export const ERROR_WINDOW_MS = 15_000;

/**
 * Settles gate answers from the conversation store: the server's reply (a message) or error on the session
 * thread. Mounted once in the shell, so a reply that arrives while World is closed still settles the flight.
 * One error settles the oldest answer still waiting.
 */
export function AnswerGateFrameHandler() {
  const threadId = useSession((s) => s.threadId);
  const lastMessageAt = useConversation((s) => s.byThread[threadId]?.lastMessageAt ?? null);
  const lastError = useConversation((s) => s.byThread[threadId]?.lastError ?? null);
  const seenMessage = useRef(lastMessageAt);
  const seenError = useRef(lastError);

  useEffect(() => {
    if (lastMessageAt === seenMessage.current) return;
    seenMessage.current = lastMessageAt;
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
  }, [lastMessageAt, threadId]);

  useEffect(() => {
    if (lastError === seenError.current) return;
    seenError.current = lastError;
    if (!lastError) return;
    const now = Date.now();
    useGateFlights.setState((s) => {
      const waiting = Object.entries(s.flights)
        .filter(([, fl]) => fl.threadId === threadId && (fl.kind === "redirect" || now - fl.sentAt <= ERROR_WINDOW_MS))
        .sort((a, b) => a[1].sentAt - b[1].sentAt)[0];
      if (!waiting) return s;
      const [id] = waiting;
      return { ...s, flights: without(s.flights, id), errors: { ...s.errors, [id]: lastError.detail } };
    });
  }, [lastError, threadId]);

  return null;
}
