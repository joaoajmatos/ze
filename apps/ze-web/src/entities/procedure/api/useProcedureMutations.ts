import { useMutation, useQueryClient } from "@tanstack/react-query";
import { workspaceFetch } from "@/entities/workspace/api/workspaceFetch";
import { queryKeys } from "@/shared/lib";
import type { ProcedureAdmissionResult, ProcedureVersion } from "../model/types";

export function useDisableProcedureMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      procedureId,
      reason,
    }: {
      procedureId: string;
      reason: string;
    }): Promise<ProcedureVersion> => {
      const res = await workspaceFetch(`/procedures/${procedureId}/disable`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      return (await res.json()) as ProcedureVersion;
    },
    onSuccess: (_data, { procedureId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureLibrary() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureDetail(procedureId) });
    },
  });
}

export function useEditProcedureMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      procedureId,
      name,
      trigger,
      preconditions,
      steps,
      success_criteria,
      limits,
      reason,
    }: {
      procedureId: string;
      name: string;
      trigger: string;
      preconditions: string[];
      steps: string[];
      success_criteria: string[];
      limits: string[];
      reason: string;
    }): Promise<ProcedureAdmissionResult> => {
      const res = await workspaceFetch(`/procedures/${procedureId}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          trigger,
          preconditions,
          steps,
          success_criteria,
          limits,
          reason,
        }),
      });
      return (await res.json()) as ProcedureAdmissionResult;
    },
    onSuccess: (_data, { procedureId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureLibrary() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureDetail(procedureId) });
    },
  });
}
