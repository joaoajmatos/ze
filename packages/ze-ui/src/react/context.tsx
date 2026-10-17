import { createContext, useContext } from "react";

export interface CardActionEvent {
  intent: string;
  ref_id: string;
  /** The card's claim subject, so `open` knows which record to navigate to. */
  subject: string;
}

export interface ChatAboutEvent {
  /** The claim's subject kind and record id; the host maps them to a screen ref. */
  subject: string;
  ref_id: string;
  title: string;
  /** The card, so the host can turn the orb toward it. */
  element: Element;
}

export interface PrimitiveRendererActions {
  onButtonAction?: (action: string) => boolean | void;
  onFormSubmit?: (formId: string, values: Record<string, string>) => boolean | void;
  onDisconnected?: () => void;
  /** Resolves false when the action was not accepted, so the card keeps its buttons. */
  onCardAction?: (action: CardActionEvent) => boolean | void | Promise<boolean | void>;
  /** When set, a claim card shows the "Chat about this" chip. */
  onChatAbout?: (event: ChatAboutEvent) => void;
}

const defaultActions: PrimitiveRendererActions = {};

export const PrimitiveRendererContext = createContext<PrimitiveRendererActions>(defaultActions);

export function usePrimitiveRendererActions(): PrimitiveRendererActions {
  return useContext(PrimitiveRendererContext);
}
