import { getMemoryGraph } from "@myguyze/ze-client";
import type { MemoryGraphResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export interface MemoryGraphFilters {
  entityType?: string;
  seedId?: string;
  limit?: number;
}

export function useMemoryGraphQuery(filters: MemoryGraphFilters = {}) {
  return useQuery({
    queryKey: queryKeys.memoryGraph(filters.entityType, filters.seedId),
    queryFn: async () => {
      const { data, error } = await getMemoryGraph({
        query: {
          limit: filters.limit ?? 50,
          entity_type: filters.entityType ?? undefined,
          seed_id: filters.seedId ?? undefined,
        },
      });
      if (error) throw error;
      return data as MemoryGraphResponse;
    },
  });
}
