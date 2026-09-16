import { useMutation, useQueryClient } from "@tanstack/react-query";
import { workspaceFetch } from "@/entities/workspace/api/workspaceFetch";
import { queryKeys } from "@/shared/lib";
import type { ProcedureAdmissionResult } from "../model/types";

export type ProcedureReviewDecision =
  | "approve"
  | "reject"
  | "needs_review"
  | "withdraw";

export function useReviewProcedureMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      candidateId,
      decision,
      reason,
    }: {
      candidateId: string;
      decision: ProcedureReviewDecision;
      reason: string;
    }): Promise<ProcedureAdmissionResult> => {
      const res = await workspaceFetch(`/procedures/candidates/${candidateId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reason }),
      });
      return (await res.json()) as ProcedureAdmissionResult;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureCandidates() });
    },
  });
}
