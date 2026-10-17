import { setHypothesisFeedback } from "@myguyze/ze-client";
import type { HypothesisFeedbackRequest } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useHypothesisFeedbackMutation() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { hypothesisId: string; feedback: HypothesisFeedbackRequest["feedback"] }>({
    mutationFn: async ({ hypothesisId, feedback }) => {
      const { error } = await setHypothesisFeedback({ path: { hypothesis_id: hypothesisId }, body: { feedback } });
      if (error) throw error;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hypotheses"] });
      void queryClient.invalidateQueries({ queryKey: ["priority-snapshot"] });
    },
  });
}
