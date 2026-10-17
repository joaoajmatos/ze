import { getContactsPage } from "@myguyze/ze-client";
import type { PluginPageResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useContactsPageQuery() {
  return useQuery<PluginPageResponse | undefined>({
    queryKey: queryKeys.contactsPage,
    queryFn: async () => {
      const { data, error } = await getContactsPage();
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}
