import type { WorkspaceRunResponse } from "@myguyze/ze-client";

const STATUS: Record<string, string> = {
  succeeded: "Finished",
  failed: "Failed",
  timed_out: "Timed out",
  cancelled: "Cancelled",
  refused: "Refused",
  in_progress: "Running",
};

const ORIGIN: Record<string, string> = {
  conversation: "From a chat",
  user: "You",
  unattended: "On its own",
};

function sentence(raw: string): string {
  const spaced = raw.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export const statusWord = (status: string): string => STATUS[status] ?? sentence(status);
export const originWord = (origin: string): string => ORIGIN[origin] ?? sentence(origin);

/** Coral is for unattended failures only; a chat or user run shows its failure in plain words. */
export function isAlarm(run: Pick<WorkspaceRunResponse, "origin" | "status">): boolean {
  return run.origin === "unattended" && (run.status === "failed" || run.status === "timed_out");
}

export const hasRunning = (runs: readonly WorkspaceRunResponse[] | undefined): boolean =>
  !!runs?.some((r) => r.status === "in_progress");
