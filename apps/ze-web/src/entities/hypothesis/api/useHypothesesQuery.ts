import { listHypotheses } from "@myguyze/ze-client";
import type { HypothesisItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export interface HypothesesOptions {
  state?: "open" | "confirmed" | "dismissed" | "all";
  entityId?: string;
  limit?: number;
}

export function useHypothesesQuery({ state = "open", entityId, limit }: HypothesesOptions = {}) {
  return useQuery<HypothesisItem[]>({
    queryKey: queryKeys.hypotheses(state, entityId),
    queryFn: async () => {
      const { data } = await listHypotheses({ query: { state, entity_id: entityId, limit } });
      return data ?? [];
    },
  });
}
