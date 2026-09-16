import { useQuery } from "@tanstack/react-query";
import { workspaceFetch } from "@/entities/workspace/api/workspaceFetch";
import { queryKeys } from "@/shared/lib";
import type { ProcedureDetail } from "../model/types";

export function useProcedureDetailQuery(procedureId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.procedureDetail(procedureId ?? ""),
    enabled: Boolean(procedureId),
    queryFn: async (): Promise<ProcedureDetail> => {
      const res = await workspaceFetch(`/procedures/${procedureId}`);
      return (await res.json()) as ProcedureDetail;
    },
  });
}
