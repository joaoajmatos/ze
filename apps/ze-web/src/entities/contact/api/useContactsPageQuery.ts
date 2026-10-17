import { getContactsPage } from "@myguyze/ze-client";
import type { PluginPageResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useContactsPageQuery() {
  return useQuery<PluginPageResponse | undefined>({
    queryKey: queryKeys.contactsPage,
    queryFn: async () => {
      const { data } = await getContactsPage();
      return data;
    },
    staleTime: 60_000,
  });
}
