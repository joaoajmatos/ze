import type { WsScreenContext } from "@myguyze/ze-client";
import { createContext, useContext, type ReactNode } from "react";

export type TurnSender = (threadId: string, text: string, options?: { explicitContext?: WsScreenContext }) => boolean;

const TurnSenderContext = createContext<TurnSender | null>(null);

/** The shell hands over the app's one send path; a feature cannot import `features/turn-stream` itself. */
export function TurnSenderProvider({ sendTurn, children }: { sendTurn: TurnSender; children: ReactNode }) {
  return <TurnSenderContext.Provider value={sendTurn}>{children}</TurnSenderContext.Provider>;
}

export function useTurnSender(): TurnSender | null {
  return useContext(TurnSenderContext);
}
