import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewGoalLearning } from "./ReviewGoalLearning";

const { useReviewGoalLearningMutation } = vi.hoisted(() => ({
  useReviewGoalLearningMutation: vi.fn(),
}));

vi.mock("@/entities/goal", () => ({
  useReviewGoalLearningMutation,
}));

const pending = {
  id: "learn-1",
  content: "Conversation practice beats drills",
  claim_kind: "inference",
  provenance: "synthesized",
  confidence: 0.4,
  status: "pending_review",
  evidence_count: 1,
  promotion_state: null,
  review_needed: true,
  created_at: new Date().toISOString(),
};

function setup(mutate = vi.fn()) {
  useReviewGoalLearningMutation.mockReturnValue({ mutate, isPending: false });
  return mutate;
}

describe("ReviewGoalLearning", () => {
  it("offers review actions on pending learnings", () => {
    setup();
    render(<ReviewGoalLearning goalId="goal-1" learning={pending} />);
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
    expect(screen.getByText("Defer")).toBeInTheDocument();
  });

  it("calls approve with the learning id", () => {
    const mutate = setup();
    render(<ReviewGoalLearning goalId="goal-1" learning={pending} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(mutate).toHaveBeenCalledWith({
      goalId: "goal-1",
      learningId: "learn-1",
      decision: "approve",
    });
  });

  it("hides actions for retracted learnings", () => {
    setup();
    render(
      <ReviewGoalLearning
        goalId="goal-1"
        learning={{ ...pending, status: "retracted", review_needed: false }}
      />,
    );
    expect(screen.queryByText("Approve")).not.toBeInTheDocument();
  });
});
