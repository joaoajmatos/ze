import { getEntityDetail } from "@myguyze/ze-client";
import type { EntityDetailResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

/** The entity's detail, or `null` when no such entity exists. */
export function useEntityDetailQuery(entityId: string | null) {
  return useQuery<EntityDetailResponse | null>({
    queryKey: queryKeys.entityDetail(entityId ?? ""),
    queryFn: async () => {
      const { data, error, response } = await getEntityDetail({ path: { entity_id: entityId! } });
      if (response?.status === 404) return null;
      if (error || !data) throw new Error("Could not load the entity");
      return data;
    },
    enabled: entityId !== null,
  });
}
