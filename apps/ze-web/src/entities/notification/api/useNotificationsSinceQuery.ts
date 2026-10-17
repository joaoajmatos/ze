import { listNotifications } from "@myguyze/ze-client";
import type { NotificationItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

/** Notifications since a visit. Not paged and never under `["notifications"]`, whose cache is rewritten as InfiniteData. */
export function useNotificationsSinceQuery(since: string) {
  return useQuery<NotificationItem[]>({
    queryKey: queryKeys.notificationsSince(since),
    queryFn: async () => {
      const { data, error } = await listNotifications({ query: { since, limit: 50, mark_read: false } });
      if (error) throw error;
      return data?.items ?? [];
    },
  });
}
