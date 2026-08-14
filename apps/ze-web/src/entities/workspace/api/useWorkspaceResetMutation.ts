import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { workspaceFetch } from "./workspaceFetch";

export function useWorkspaceResetMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    { confirmation_id?: string; reset?: boolean },
    Error,
    { confirmationId?: string; choice?: "approve" | "deny" } | void
  >({
    mutationFn: async (input) => {
      const body =
        input && input.confirmationId && input.choice
          ? { confirmation_id: input.confirmationId, choice: input.choice }
          : undefined;
      const res = await workspaceFetch("/workspace/reset", {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      return res.json() as Promise<{ confirmation_id?: string; reset?: boolean }>;
    },
    onSuccess: (data) => {
      if (data.reset) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.workspace() });
        void queryClient.invalidateQueries({ queryKey: queryKeys.workspaceFiles() });
        void queryClient.invalidateQueries({ queryKey: queryKeys.workspaceRuns() });
      }
    },
  });
}
