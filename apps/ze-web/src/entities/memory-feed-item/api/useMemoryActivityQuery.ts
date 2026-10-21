import { getMemoryActivity } from "@myguyze/ze-client";
import type { MemoryActivityResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";

export function useMemoryActivityQuery(start: Date | undefined, end: Date | undefined) {
  return useQuery({
    queryKey: ["memory-activity", start?.toISOString(), end?.toISOString()],
    queryFn: async () => {
      const { data, error } = await getMemoryActivity({
        query: { start: start!.toISOString(), end: end!.toISOString() },
      });
      if (error || !data) throw error ?? new Error("Failed to load memory activity");
      return data as MemoryActivityResponse;
    },
    enabled: Boolean(start && end),
    staleTime: 60_000,
  });
}
