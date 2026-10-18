import { listSessions } from "@myguyze/ze-client";
import type { SessionListResponse } from "@myguyze/ze-client";
import { useInfiniteQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useSessionsQuery(limit = 30) {
  return useInfiniteQuery({
    queryKey: queryKeys.sessions,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await listSessions({
        query: {
          limit,
          before: pageParam ?? undefined,
        },
      });
      if (error) throw error;
      return data as SessionListResponse;
    },
    getNextPageParam: (lastPage) => lastPage?.next_before ?? undefined,
    initialPageParam: undefined as string | undefined,
  });
}
