import { listNotifications } from "@myguyze/ze-client";
import type { NotificationItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

const OUTCOMES = ["held", "suppressed", "failed"] as const;

/** Pushes that did not reach the user as sent. Outside `["notifications"]` so the bell's invalidations skip it. */
export function useNotificationOutcomesQuery() {
  return useQuery<NotificationItem[]>({
    queryKey: queryKeys.notificationsDelivery(OUTCOMES.join(",")),
    queryFn: async () => {
      const { data, error } = await listNotifications({ query: { delivery: [...OUTCOMES], limit: 10 } });
      if (error) throw error;
      return data?.items ?? [];
    },
  });
}
