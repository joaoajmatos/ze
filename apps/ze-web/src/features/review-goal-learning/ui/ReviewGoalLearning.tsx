import type { LearningResponse } from "@myguyze/ze-client";
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
    <span className="acts">
      <button type="button" className="ctl" disabled={review.isPending}
        onClick={() =>
          review.mutate({
            goalId,
            learningId: learning.id,
            decision: "approve",
          })
        }
      >
        Approve
      </button>
      <button type="button" className="ctl" disabled={review.isPending}
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
      </button>
      <button type="button" className="ctl" disabled={review.isPending}
        onClick={() =>
          review.mutate({
            goalId,
            learningId: learning.id,
            decision: "defer",
          })
        }
      >
        Defer
      </button>
    </span>
  );
}
