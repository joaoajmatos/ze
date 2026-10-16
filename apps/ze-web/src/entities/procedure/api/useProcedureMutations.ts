import { disableProcedure, editProcedure } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
      const { data, error } = await disableProcedure({
        path: { procedure_id: procedureId },
        body: { reason },
      });
      if (error) throw error;
      return data!;
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
      ...body
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
      const { data, error } = await editProcedure({
        path: { procedure_id: procedureId },
        body,
      });
      if (error) throw error;
      return data!;
    },
    onSuccess: (_data, { procedureId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureLibrary() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureDetail(procedureId) });
    },
  });
}
