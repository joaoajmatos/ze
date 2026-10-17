import type { LucideIcon } from "lucide-react";
import { Brain, Globe, MessageCircle, ShieldCheck, Workflow } from "lucide-react";
import { redirectHintPath } from "@/shared/lib/redirect-hint";

export type PlaceId = "world" | "ask" | "doing" | "mind" | "governance";

export interface Place {
  id: PlaceId;
  path: string;
  label: string;
  icon: LucideIcon;
}

/** The five places, in navigation order. */
export const places: readonly Place[] = [
  { id: "world", path: "/", label: "World", icon: Globe },
  { id: "ask", path: "/ask", label: "Ask", icon: MessageCircle },
  { id: "doing", path: "/doing", label: "Doing", icon: Workflow },
  { id: "mind", path: "/mind", label: "Mind", icon: Brain },
  { id: "governance", path: "/governance", label: "Governance", icon: ShieldCheck },
];

/** The place owning `pathname`, or null for plugin pages, the design reference and unknown paths. */
export function placeOf(pathname: string): Place | null {
  if (pathname === "/") return places[0];
  const segment = pathname.split("/")[1];
  if (segment === "world") return places[0];
  return places.find((p) => p.id !== "world" && p.path === `/${segment}`) ?? null;
}

/** Old routes (ntfy links, bookmarks) and where they land; `:param` segments carry across. */
export const redirects: readonly { from: string; to: string }[] = [
  { from: "/loops", to: "/" },
  { from: "/priority", to: "/world/priority" },
  { from: "/goals", to: "/doing/goals" },
  { from: "/goals/:goalId", to: "/doing/goals/:goalId" },
  { from: "/workflows", to: "/doing/workflows" },
  { from: "/workflows/:workflowId", to: "/doing/workflows/:workflowId" },
  { from: "/skills", to: "/doing/skills" },
  { from: "/procedures", to: "/mind" },
  { from: "/doing/procedures", to: "/mind" },
  { from: "/contacts", to: "/mind" },
  { from: "/mind/graph", to: "/mind" },
  { from: "/workspace", to: "/doing/workspace" },
  { from: "/brain-memory", to: "/mind" },
  { from: "/brain-graph", to: "/mind" },
  { from: "/costs", to: "/governance" },
  { from: "/data", to: "/governance/data" },
  { from: "/settings", to: "/governance/settings" },
];

export function goalsPath(): string {
  return "/doing/goals";
}

export function workflowsPath(): string {
  return "/doing/workflows";
}

export function goalPath(goalId: string): string {
  return `/doing/goals/${goalId}`;
}

export function workflowPath(workflowId: string, executionId?: string): string {
  const base = `/doing/workflows/${workflowId}`;
  return executionId ? `${base}?execution=${encodeURIComponent(executionId)}` : base;
}

export function askPath(threadId?: string): string {
  return threadId ? `/ask/${threadId}` : "/ask";
}

/** Hash target for export/import/delete in Settings. */
export const settingsDataSectionId = "your-data";

export function settingsDataPath(): string {
  return redirectHintPath("/governance/settings", settingsDataSectionId);
}
