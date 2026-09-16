import { useQuery } from "@tanstack/react-query";
import { workspaceFetch } from "@/entities/workspace/api/workspaceFetch";
import { queryKeys } from "@/shared/lib";
import type { ProcedureSummary } from "../model/types";

export function useProcedureLibraryQuery() {
  return useQuery({
    queryKey: queryKeys.procedureLibrary(),
    queryFn: async (): Promise<ProcedureSummary[]> => {
      const res = await workspaceFetch("/procedures/library");
      return (await res.json()) as ProcedureSummary[];
    },
  });
}
