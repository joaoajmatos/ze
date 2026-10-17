import { parsePrimitiveTree, type PrimitiveTree } from "@myguyze/ze-ui";
import { PrimitiveTreeRenderer } from "@myguyze/ze-ui/react";
import { useMemo } from "react";
import { useCardActions } from "../api/useCardActions";
import { usePrimitiveRendererActions } from "../api/usePrimitiveRendererActions";

export function ConnectedPrimitiveTree({ components }: { components: unknown }) {
  const baseActions = usePrimitiveRendererActions();
  const onCardAction = useCardActions();
  const actions = useMemo(() => ({ ...baseActions, onCardAction }), [baseActions, onCardAction]);

  let nodes: PrimitiveTree;
  try {
    nodes = parsePrimitiveTree(components);
  } catch {
    return null;
  }

  return <PrimitiveTreeRenderer nodes={nodes} actions={actions} />;
}
