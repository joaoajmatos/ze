import { createContext, useContext, type ReactNode } from "react";

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

/**
 * Class names a host supplies so the renderer carries no app CSS. A mapped key replaces the renderer's
 * own classes for that part; an unmapped key keeps them, so plugin hosts without a map look as before.
 */
export interface PrimitiveClassNames {
  heading?: string;
  subheading?: string;
  body?: string;
  label?: string;
  caption?: string;
  code?: string;
  /** Added to a text with `color: "muted"`. */
  muted?: string;
  badge?: string;
  /** A `col` with `variant: "card"` or `"section"`. */
  card?: string;
  progressTrack?: string;
  progressFill?: string;
  table?: string;
  steps?: string;
  connections?: string;
  button?: string;
  buttonPrimary?: string;
  buttonDanger?: string;
  claimCard?: string;
  claimTimeline?: string;
  divider?: string;
}

export interface PrimitiveRendererActions {
  classNames?: PrimitiveClassNames;
  /** Draws a `headline`; the host passes its dot-matrix. Plain text when absent. */
  renderHeadline?: (text: string) => ReactNode;
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
