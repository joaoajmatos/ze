import type { WsScreenContext } from "@myguyze/ze-client";
import { placeOf } from "@/shared/config";

/** Where the person is, as the chat context the engine turns into a screen note. */
export function resolveScreenContext(pathname: string, search: string): WsScreenContext {
  const [, first, second, third] = pathname.split("/");
  const place = placeOf(pathname);
  if (!place) return { screen: first || "world" };

  const screen = place.id === "world" ? (first === "world" && second ? `world.${second}` : "world") : second && place.id !== "ask" ? `${place.id}.${second}` : place.id;
  const context: WsScreenContext = { screen };

  if (place.id === "doing" && second === "goals" && third) context.goal_id = third;
  if (place.id === "doing" && second === "workflows" && third) {
    context.workflow_id = third;
    const execution = new URLSearchParams(search).get("execution");
    if (execution) context.execution_id = execution;
  }
  return context;
}
