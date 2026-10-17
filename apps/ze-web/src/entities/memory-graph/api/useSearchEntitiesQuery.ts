import { searchEntities } from "@myguyze/ze-client";
import type { GraphEntityNode } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useSearchEntitiesQuery(q: string, entityType?: string) {
  const text = q.trim();
  return useQuery<GraphEntityNode[]>({
    queryKey: queryKeys.entitySearch(text, entityType),
    queryFn: async () => {
      const { data } = await searchEntities({ query: { q: text, entity_type: entityType, limit: 20 } });
      return data ?? [];
    },
    enabled: text.length >= 1,
  });
}
