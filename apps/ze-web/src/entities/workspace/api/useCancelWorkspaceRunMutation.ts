import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { WorkspaceRunItem } from "./types";
import { workspaceFetch } from "./workspaceFetch";

export function useCancelWorkspaceRunMutation() {
  const queryClient = useQueryClient();
  return useMutation<WorkspaceRunItem, Error, string>({
    mutationFn: async (runId) => {
      const res = await workspaceFetch(`/workspace/runs/${runId}/cancel`, {
        method: "POST",
      });
      return res.json() as Promise<WorkspaceRunItem>;
    },
    onSuccess: () => {
      // Matches every origin-filtered variant of ["workspace-runs", origin] —
      // a single-element prefix key so invalidation isn't tied to whichever
      // origin filter happens to be active on screen.
      void queryClient.invalidateQueries({ queryKey: ["workspace-runs"] });
    },
  });
}
