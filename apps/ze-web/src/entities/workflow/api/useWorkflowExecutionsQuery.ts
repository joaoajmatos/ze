import { listWorkflowExecutions } from "@myguyze/ze-client";
import type { WorkflowExecutionResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useWorkflowExecutionsQuery(workflowId: string) {
  return useQuery<WorkflowExecutionResponse[]>({
    queryKey: queryKeys.workflowExecutions(workflowId),
    queryFn: async () => {
      const { data, error } = await listWorkflowExecutions({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data ?? [];
    },
    enabled: !!workflowId,
  });
}
