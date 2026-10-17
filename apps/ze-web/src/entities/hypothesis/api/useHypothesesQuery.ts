import { listHypotheses } from "@myguyze/ze-client";
import type { HypothesisItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

type HypothesisState = "open" | "confirmed" | "dismissed" | "all";

export function useHypothesesQuery(options?: { state?: HypothesisState; entityId?: string; limit?: number }) {
  const state = options?.state ?? "open";
  const entityId = options?.entityId;

  return useQuery<HypothesisItem[]>({
    queryKey: queryKeys.hypotheses(state, entityId),
    queryFn: async () => {
      const { data, error } = await listHypotheses({
        query: { state, entity_id: entityId, limit: options?.limit },
      });
      if (error) throw error;
      return data ?? [];
    },
  });
}
