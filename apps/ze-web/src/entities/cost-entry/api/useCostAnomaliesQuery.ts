import { getCostAnomalies } from "@myguyze/ze-client";
import type { CostAnomaliesResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useCostAnomaliesQuery() {
  return useQuery<CostAnomaliesResponse>({
    queryKey: queryKeys.costAnomalies,
    queryFn: async () => {
      const { data, error } = await getCostAnomalies();
      if (error || !data) throw error ?? new Error("Failed to load cost anomalies");
      return data;
    },
  });
}
