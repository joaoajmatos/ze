import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewProcedureCandidate } from "@myguyze/ze-client";
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
      const { data, error } = await reviewProcedureCandidate({
        path: { candidate_id: candidateId },
        body: { decision, reason },
      });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.procedureCandidates() });
    },
  });
}
