import { listProcedureLibrary } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { ProcedureSummary } from "../model/types";

export function useProcedureLibraryQuery() {
  return useQuery({
    queryKey: queryKeys.procedureLibrary(),
    queryFn: async (): Promise<ProcedureSummary[]> => {
      const { data, error } = await listProcedureLibrary();
      if (error) throw error;
      return data ?? [];
    },
  });
}
