import { listLoops } from "@myguyze/ze-client";
import type { LoopListItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

type LoopStateName = "suspected" | "active" | "drifting" | "closed" | "dropped";

export function useLoopsQuery(state?: LoopStateName) {
  return useQuery<LoopListItem[]>({
    queryKey: queryKeys.loops(state),
    queryFn: async () => {
      const { data, error } = await listLoops({ query: state ? { state: [state] } : undefined });
      if (error) throw error;
      return data ?? [];
    },
  });
}
