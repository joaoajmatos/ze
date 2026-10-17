import { getMemoryTimelineBounds } from "@myguyze/ze-client";
import type { TimelineBoundsResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";

export function useMemoryTimelineBoundsQuery() {
  return useQuery({
    queryKey: ["memory-timeline-bounds"],
    queryFn: async () => {
      const { data, error } = await getMemoryTimelineBounds({});
      if (error) throw error;
      return data as TimelineBoundsResponse;
    },
    staleTime: 60_000,
  });
}
