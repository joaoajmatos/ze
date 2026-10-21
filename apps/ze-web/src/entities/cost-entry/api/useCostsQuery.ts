import { getCostSummary } from "@myguyze/ze-client";
import type { WebCostSummaryResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useCostsQuery() {
  return useQuery<WebCostSummaryResponse>({
    queryKey: queryKeys.costs,
    queryFn: async () => {
      const { data, error } = await getCostSummary();
      if (error || !data) throw error ?? new Error("Failed to load costs");
      return data;
    },
  });
}
