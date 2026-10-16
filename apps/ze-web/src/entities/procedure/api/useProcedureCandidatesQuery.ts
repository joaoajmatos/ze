import { listProcedureCandidates } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { ProcedureCandidate } from "../model/types";

export function useProcedureCandidatesQuery() {
  return useQuery({
    queryKey: queryKeys.procedureCandidates(),
    queryFn: async (): Promise<ProcedureCandidate[]> => {
      const { data, error } = await listProcedureCandidates();
      if (error) throw error;
      return data ?? [];
    },
  });
}
