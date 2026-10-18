import { getWorkflow } from "@myguyze/ze-client";
import type { WorkflowDetailResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useWorkflowDetailQuery(workflowId: string) {
  return useQuery<WorkflowDetailResponse>({
    queryKey: queryKeys.workflowDetail(workflowId),
    queryFn: async () => {
      const { data, error } = await getWorkflow({ path: { workflow_id: workflowId } });
      if (error || !data) throw error ?? new Error("Workflow not found");
      return data;
    },
    enabled: !!workflowId,
  });
}
