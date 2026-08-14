import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { WorkspaceMode } from "./types";
import { workspaceFetch } from "./workspaceFetch";

export function useWorkspaceModeMutation() {
  const queryClient = useQueryClient();
  return useMutation<{ mode: WorkspaceMode }, Error, WorkspaceMode>({
    mutationFn: async (mode) => {
      const res = await workspaceFetch("/workspace/mode", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      return res.json() as Promise<{ mode: WorkspaceMode }>;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.workspace() });
    },
  });
}
