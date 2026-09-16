import { reviewGoalLearning } from "@myguyze/ze-client";
import type { LearningResponse } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export type GoalLearningReviewDecision = "approve" | "reject" | "correct" | "defer";

export function useReviewGoalLearningMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    LearningResponse,
    Error,
    {
      goalId: string;
      learningId: string;
      decision: GoalLearningReviewDecision;
      rationale?: string;
      correctedContent?: string;
    }
  >({
    mutationFn: async ({ goalId, learningId, decision, rationale, correctedContent }) => {
      const { data, error } = await reviewGoalLearning({
        path: { goal_id: goalId, learning_id: learningId },
        body: {
          decision,
          rationale,
          corrected_content: correctedContent,
        },
      });
      if (error) throw error;
      return data!;
    },
    onSuccess: (_data, { goalId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.goalDetail(goalId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.goals });
    },
  });
}
