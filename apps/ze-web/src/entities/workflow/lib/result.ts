import type { WorkflowExecutionResponse } from "@myguyze/ze-client";

export type LastResult =
  | { kind: "unknown" }
  | { kind: "never" }
  | { kind: "running" }
  | { kind: "ok" }
  | { kind: "cancelled" }
  | { kind: "held" }
  | { kind: "other"; text: string }
  | { kind: "failed"; text: string };

/**
 * The workflow's last result, read from its newest execution only. `undefined` means the executions were not
 * fetched, which is not the same as none: only a fetched empty list is "never".
 */
export function lastResult(executions: readonly WorkflowExecutionResponse[] | undefined): LastResult {
  if (!executions) return { kind: "unknown" };
  if (executions.length === 0) return { kind: "never" };
  const latest = [...executions].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  switch (latest.status) {
    case "running":
      return { kind: "running" };
    case "completed":
      return { kind: "ok" };
    case "failed":
      return { kind: "failed", text: latest.failure_summary ?? "Failed" };
    case "cancelled":
      return { kind: "cancelled" };
    case "held":
      return { kind: "held" };
    default: {
      const spaced = latest.status.replace(/_/g, " ");
      return { kind: "other", text: spaced.charAt(0).toUpperCase() + spaced.slice(1) };
    }
  }
}
