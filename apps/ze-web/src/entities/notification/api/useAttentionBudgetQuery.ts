import { getAttentionBudget } from "@myguyze/ze-client";
import type { AttentionBudgetResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useAttentionBudgetQuery() {
  return useQuery<AttentionBudgetResponse>({
    queryKey: queryKeys.attentionBudget,
    queryFn: async () => {
      const { data, error } = await getAttentionBudget();
      if (error) throw error;
      return data!;
    },
  });
}
