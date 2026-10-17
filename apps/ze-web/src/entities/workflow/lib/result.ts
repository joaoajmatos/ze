import type { WorkflowExecutionResponse } from "@myguyze/ze-client";

export type LastResult =
  | { kind: "never" }
  | { kind: "running" }
  | { kind: "ok" }
  | { kind: "failed"; text: string };

/** The workflow's last result, read from its newest execution only. */
export function lastResult(executions: readonly WorkflowExecutionResponse[] | undefined): LastResult {
  if (!executions || executions.length === 0) return { kind: "never" };
  const latest = [...executions].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (latest.status === "running") return { kind: "running" };
  if (latest.status === "failed") return { kind: "failed", text: latest.failure_summary ?? "Failed" };
  return { kind: "ok" };
}
