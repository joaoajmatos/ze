import { useQuery } from "@tanstack/react-query";
import { getProcedure } from "@myguyze/ze-client";
import { queryKeys } from "@/shared/lib";
import type { ProcedureDetail } from "../model/types";

export function useProcedureDetailQuery(procedureId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.procedureDetail(procedureId ?? ""),
    enabled: Boolean(procedureId),
    queryFn: async (): Promise<ProcedureDetail> => {
      const { data, error } = await getProcedure({ path: { procedure_id: procedureId! } });
      if (error) throw error;
      return data!;
    },
  });
}
