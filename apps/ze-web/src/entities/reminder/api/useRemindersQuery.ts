import { listReminders } from "@myguyze/ze-client";
import type { ReminderItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

type ReminderStatus = "upcoming" | "overdue" | "fired" | "all";

export function useRemindersQuery(options?: { status?: ReminderStatus; limit?: number }) {
  const status = options?.status ?? "upcoming";
  const limit = options?.limit;

  return useQuery<ReminderItem[]>({
    queryKey: queryKeys.reminders(status),
    queryFn: async () => {
      const { data, error } = await listReminders({ query: { status, limit } });
      if (error) throw error;
      return data ?? [];
    },
  });
}
