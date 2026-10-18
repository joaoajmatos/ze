import type { WsScreenRef } from "@myguyze/ze-client";
import { PrimitiveTreeRenderer } from "@myguyze/ze-ui/react";
import { useMemo } from "react";
import { useCardActions } from "../api/useCardActions";
import { usePrimitiveActions } from "../api/usePrimitiveActions";
import { HUD_CLASS_NAMES, renderHudHeadline } from "../lib/hud-class-names";
import { parseTree } from "../lib/parseTree";
import { TreeNote } from "./TreeNote";

interface ConnectedPrimitiveTreeProps {
  components: unknown;
  /** The `ui_version` the tree arrived with. Absent means it was stored before the typed-action contract. */
  uiVersion?: string | null;
  /** Wired by the widget that owns the chat; a claim card shows "Chat about this" when it is set. */
  onChatAbout?: (ref: WsScreenRef, element: Element) => void;
}

export function ConnectedPrimitiveTree({ components, uiVersion, onChatAbout }: ConnectedPrimitiveTreeProps) {
  const baseActions = usePrimitiveActions();
  const onCardAction = useCardActions();
  const actions = useMemo(
    () => ({
      ...baseActions,
      classNames: HUD_CLASS_NAMES,
      renderHeadline: renderHudHeadline,
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

  const parsed = parseTree(components, uiVersion);
  if (parsed.status !== "ok") return <TreeNote status={parsed.status} />;
  return <PrimitiveTreeRenderer nodes={parsed.nodes} actions={actions} />;
}
