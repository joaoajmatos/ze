import { getPrioritySnapshot } from "@myguyze/ze-client";
import type { PrioritySnapshotItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function usePrioritySnapshotQuery() {
  return useQuery<PrioritySnapshotItem[]>({
    queryKey: queryKeys.prioritySnapshot(),
    queryFn: async () => {
      const { data } = await getPrioritySnapshot();
      return data ?? [];
    },
  });
}
