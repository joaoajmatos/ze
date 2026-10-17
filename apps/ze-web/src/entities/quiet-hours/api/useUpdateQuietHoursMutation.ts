import { updateQuietHours } from "@myguyze/ze-client";
import type { QuietHoursUpdate } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useUpdateQuietHoursMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: QuietHoursUpdate) => {
      const { data, error } = await updateQuietHours({ body });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.quietHours });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.attentionBudget,
      });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications-delivery"] });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.unreadNotificationCount,
      });
    },
  });
}
