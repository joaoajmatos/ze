import { Button } from "@/shared/ui";
import type { ProcedureCandidate } from "@/entities/procedure";
import { useReviewProcedureMutation } from "@/entities/procedure";

interface ReviewProcedureCandidateProps {
  candidate: ProcedureCandidate;
}

export function ReviewProcedureCandidate({ candidate }: ReviewProcedureCandidateProps) {
  const review = useReviewProcedureMutation();
  const needsReview = candidate.status === "pending" || candidate.status === "needs_review";

  if (!needsReview) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={review.isPending}
        onClick={() =>
          review.mutate({
            candidateId: candidate.id,
            decision: "approve",
            reason: "approved from memory review",
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
            candidateId: candidate.id,
            decision: "reject",
            reason: "rejected from memory review",
          })
        }
      >
        Reject
      </Button>
    </div>
  );
}
