import { getQuietHours } from "@myguyze/ze-client";
import type { QuietHoursResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useQuietHoursQuery() {
  return useQuery<QuietHoursResponse>({
    queryKey: queryKeys.quietHours,
    queryFn: async () => {
      const { data, error } = await getQuietHours();
      if (error) throw error;
      return data!;
    },
  });
}
