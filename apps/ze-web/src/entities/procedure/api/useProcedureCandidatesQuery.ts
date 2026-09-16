import { useQuery } from "@tanstack/react-query";
import { workspaceFetch } from "@/entities/workspace/api/workspaceFetch";
import { queryKeys } from "@/shared/lib";
import type { ProcedureCandidate } from "../model/types";

export function useProcedureCandidatesQuery() {
  return useQuery({
    queryKey: queryKeys.procedureCandidates(),
    queryFn: async (): Promise<ProcedureCandidate[]> => {
      const res = await workspaceFetch("/procedures/candidates");
      return (await res.json()) as ProcedureCandidate[];
    },
  });
}
