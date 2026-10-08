import { getRoute } from "@/shared/config";
import { humanizeIdentifier } from "@/shared/lib/humanize";

interface ResolveInput {
  pathname: string;
  /** Screen a page registered through the overlay store. */
  screen: string;
  entityId?: string;
  overridePath?: string;
}

export interface ResolvedScreen {
  /** Human-readable panel title. */
  label: string;
  /** Machine id sent as chat context. */
  contextScreen: string;
  entityId?: string;
}

/**
 * The overlay describes where the person is from the current route. A page-registered
 * screen only wins for entity-scoped context (a goal, a workflow) or for routes the
 * nav does not know about (plugin pages), and only on the route that registered it.
 */
export function resolveOverlayScreen({
  pathname,
  screen,
  entityId,
  overridePath,
}: ResolveInput): ResolvedScreen {
  const route = getRoute(pathname);
  const registered = overridePath === pathname;

  if (registered && entityId) {
    return { label: humanizeIdentifier(capitalize(screen)), contextScreen: screen, entityId };
  }
  if (route) {
    return { label: route.label, contextScreen: route.index ? "chat" : route.path };
  }
  if (registered) {
    return { label: humanizeIdentifier(capitalize(screen)), contextScreen: screen };
  }
  const segment = pathname.replace(/^\//, "").split("/")[0] || "chat";
  return { label: humanizeIdentifier(capitalize(segment)), contextScreen: segment };
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
