import type { LearningResponse } from "@myguyze/ze-client";
import { Button } from "@/shared/ui";
import { useReviewGoalLearningMutation } from "@/entities/goal";

interface ReviewGoalLearningProps {
  goalId: string;
  learning: LearningResponse;
}

export function ReviewGoalLearning({ goalId, learning }: ReviewGoalLearningProps) {
  const review = useReviewGoalLearningMutation();
  const needsReview =
    learning.status === "pending_review" || learning.status === "review_needed";

  if (!needsReview) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 pl-4">
      <Button
        size="sm"
        variant="outline"
        disabled={review.isPending}
        onClick={() =>
          review.mutate({
            goalId,
            learningId: learning.id,
            decision: "approve",
          })
        }
      >
        Approve
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={review.isPending}
        onClick={() =>
          review.mutate({
            goalId,
            learningId: learning.id,
            decision: "reject",
            rationale: "rejected from goal detail",
          })
        }
      >
        Reject
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={review.isPending}
        onClick={() =>
          review.mutate({
            goalId,
            learningId: learning.id,
            decision: "defer",
          })
        }
      >
        Defer
      </Button>
    </div>
  );
}
