import { listWorkflowExecutions } from "@myguyze/ze-client";
import type { WorkflowExecutionResponse } from "@myguyze/ze-client";
import { useQueries } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

const MAX_WORKFLOWS = 10;
const RUNS_PER_WORKFLOW = 5;

export interface LatestExecutions {
  byWorkflow: Record<string, WorkflowExecutionResponse[]>;
  loading: boolean;
  error: boolean;
}

/** Latest runs of up to 10 workflows. The list route has no limit parameter, so each list is cut client-side. */
export function useLatestExecutionsQuery(workflowIds: string[]): LatestExecutions {
  const ids = workflowIds.slice(0, MAX_WORKFLOWS);
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.workflowExecutions(id),
      queryFn: async () => {
        const { data, error } = await listWorkflowExecutions({ path: { workflow_id: id } });
        if (error) throw error;
        return data ?? [];
      },
    })),
  });

  const byWorkflow: Record<string, WorkflowExecutionResponse[]> = {};
  results.forEach((r, i) => {
    if (r.data) byWorkflow[ids[i]] = r.data.slice(0, RUNS_PER_WORKFLOW);
  });
  return {
    byWorkflow,
    loading: results.some((r) => r.isPending),
    error: results.some((r) => r.isError),
  };
}
