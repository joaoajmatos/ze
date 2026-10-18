import { listWorkflowRevisions } from "@myguyze/ze-client";
import type { WorkflowRevisionResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useWorkflowRevisionsQuery(workflowId: string) {
  return useQuery<WorkflowRevisionResponse[]>({
    queryKey: queryKeys.workflowRevisions(workflowId),
    queryFn: async () => {
      const { data, error } = await listWorkflowRevisions({ path: { workflow_id: workflowId } });
      if (error) throw error;
      return data ?? [];
    },
    enabled: !!workflowId,
  });
}
