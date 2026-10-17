import { createContext, useContext } from "react";

export interface CardActionEvent {
  intent: string;
  ref_id: string;
  /** The card's claim subject, so `open` knows which record to navigate to. */
  subject: string;
}

export interface PrimitiveRendererActions {
  onButtonAction?: (action: string) => boolean | void;
  onFormSubmit?: (formId: string, values: Record<string, string>) => boolean | void;
  onDisconnected?: () => void;
  onCardAction?: (action: CardActionEvent) => void;
}

const defaultActions: PrimitiveRendererActions = {};

export const PrimitiveRendererContext = createContext<PrimitiveRendererActions>(defaultActions);

export function usePrimitiveRendererActions(): PrimitiveRendererActions {
  return useContext(PrimitiveRendererContext);
}
