import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { applyRating, patchFeedback, restoreFeedback } from "../lib/feedbackCache";
import type { MessageFeedback, SetFeedbackArgs } from "../model/types";
import { putMessageFeedback } from "./feedbackApi";

const MUTATION_KEY = ["set-message-feedback"] as const;

type Snapshot = ReturnType<typeof patchFeedback>;

export function useSetMessageFeedbackMutation() {
  const queryClient = useQueryClient();

  return useMutation<MessageFeedback, Error, SetFeedbackArgs, { snapshot: Snapshot }>({
    mutationKey: MUTATION_KEY,
    mutationFn: (args) => putMessageFeedback(args),
    onMutate: async ({ messageId, rating }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.messageFeedbackAll });
      return { snapshot: patchFeedback(queryClient, messageId, (v) => applyRating(v, rating)) };
    },
    onError: (_err, _args, ctx) => {
      if (ctx) restoreFeedback(queryClient, ctx.snapshot);
    },
    onSuccess: (view, { messageId }) => {
      patchFeedback(queryClient, messageId, (v) => ({ ...v, ...view }));
    },
    onSettled: () => {
      // Refetch only once the last in-flight press lands, so a stale read never
      // overwrites a newer optimistic rating.
      if (queryClient.isMutating({ mutationKey: MUTATION_KEY }) <= 1) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.messageFeedbackAll });
      }
    },
  });
}
