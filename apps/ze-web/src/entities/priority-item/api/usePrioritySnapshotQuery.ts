import { getPrioritySnapshot } from "@myguyze/ze-client";
import type { PrioritySnapshotItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export interface PrioritySnapshotData {
  items: PrioritySnapshotItem[];
  sourcesFailed: string[];
}

export function usePrioritySnapshotQuery() {
  return useQuery<PrioritySnapshotData>({
    queryKey: queryKeys.prioritySnapshot(),
    queryFn: async () => {
      const { data } = await getPrioritySnapshot();
      return {
        items: data?.items ?? [],
        sourcesFailed: data?.sources_failed ?? [],
      };
    },
  });
}
