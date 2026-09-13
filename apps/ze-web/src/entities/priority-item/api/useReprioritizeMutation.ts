import { submitPriorityOverride, unpinPriorityOverride } from "@myguyze/ze-client";
import type { PriorityOverrideRequestSchema, PrioritySnapshotItem } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useReprioritizeMutation() {
  const queryClient = useQueryClient();

  return useMutation<PrioritySnapshotItem, Error, PriorityOverrideRequestSchema>({
    mutationFn: async (request) => {
      const { data, error } = await submitPriorityOverride({ body: request });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prioritySnapshot() });
    },
  });
}

export function useUnpinPriorityOverrideMutation() {
  const queryClient = useQueryClient();

  return useMutation<PrioritySnapshotItem, Error, { overrideId: string }>({
    mutationFn: async ({ overrideId }) => {
      const { data, error } = await unpinPriorityOverride({
        path: { override_id: overrideId },
      });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prioritySnapshot() });
    },
  });
}
