import { cancelWorkspaceRun } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export type CancelOutcome = { outcome: "cancelled" } | { outcome: "gone"; line: string };

export function useCancelWorkspaceRunMutation() {
  const queryClient = useQueryClient();
  const refetch = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.workspaceRuns() });
    void queryClient.invalidateQueries({ queryKey: queryKeys.workspace() });
  };
  return useMutation<CancelOutcome, unknown, string>({
    mutationFn: async (runId) => {
      const { error, response } = await cancelWorkspaceRun({ path: { run_id: runId } });
      if (!error) return { outcome: "cancelled" };
      if (response?.status === 409) return { outcome: "gone", line: "already finished" };
      if (response?.status === 404) return { outcome: "gone", line: "no longer exists" };
      throw error;
    },
    onSuccess: refetch,
  });
}
