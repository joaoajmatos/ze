import type { WsScreenRef } from "@myguyze/ze-client";
import { parsePrimitiveTree, type PrimitiveTree } from "@myguyze/ze-ui";
import { PrimitiveTreeRenderer } from "@myguyze/ze-ui/react";
import { useMemo } from "react";
import { useCardActions } from "../api/useCardActions";
import { usePrimitiveRendererActions } from "../api/usePrimitiveRendererActions";

interface ConnectedPrimitiveTreeProps {
  components: unknown;
  /** Wired by the widget that owns the chat; a claim card shows "Chat about this" when it is set. */
  onChatAbout?: (ref: WsScreenRef, element: Element) => void;
}

export function ConnectedPrimitiveTree({ components, onChatAbout }: ConnectedPrimitiveTreeProps) {
  const baseActions = usePrimitiveRendererActions();
  const onCardAction = useCardActions();
  const actions = useMemo(
    () => ({
      ...baseActions,
      onCardAction,
      ...(onChatAbout
        ? {
            onChatAbout: (event: { subject: string; ref_id: string; title: string; element: Element }) =>
              onChatAbout(
                { kind: event.subject, id: event.ref_id, label: event.title, component: "claim_card" },
                event.element,
              ),
          }
        : {}),
    }),
    [baseActions, onCardAction, onChatAbout],
  );

  let nodes: PrimitiveTree;
  try {
    nodes = parsePrimitiveTree(components);
  } catch {
    return null;
  }

  return <PrimitiveTreeRenderer nodes={nodes} actions={actions} />;
}
