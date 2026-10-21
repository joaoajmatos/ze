import { listDataDomains } from "@myguyze/ze-client";
import type { DataDomainsResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useDataDomainsQuery() {
  return useQuery<DataDomainsResponse>({
    queryKey: queryKeys.dataDomains(),
    queryFn: async () => {
      const { data, error } = await listDataDomains();
      if (error || !data) throw error ?? new Error("Failed to load data domains");
      return data;
    },
  });
}
