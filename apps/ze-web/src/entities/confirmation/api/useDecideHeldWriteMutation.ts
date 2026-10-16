import { decideHeldWrite } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

interface HeldWriteDecision {
  requestId: string;
  choice: "approve" | "deny";
  edits?: Record<string, string>;
}

export function useDecideHeldWriteMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ requestId, choice, edits }: HeldWriteDecision) => {
      const { data, error } = await decideHeldWrite({
        path: { request_id: requestId },
        body: { choice, ...(edits ? { edits } : {}) },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.heldWrites });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.unreadNotificationCount });
    },
  });
}
