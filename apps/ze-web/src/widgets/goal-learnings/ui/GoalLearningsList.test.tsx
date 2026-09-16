import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GoalLearningsList } from "./GoalLearningsList";

const inference = {
  id: "learn-1",
  content: "Conversation practice beats drills",
  claim_kind: "inference",
  provenance: "synthesized",
  confidence: 0.4,
  status: "pending_review",
  evidence_count: 2,
  promotion_state: null,
  review_needed: true,
  created_at: new Date().toISOString(),
};

const retracted = {
  ...inference,
  id: "learn-2",
  status: "retracted",
  review_needed: false,
};

describe("GoalLearningsList", () => {
  it("shows doctrine badges, evidence counts, and retracted history", () => {
    render(
      <GoalLearningsList
        learnings={[inference, retracted]}
        reviewSlot={(learning) =>
          learning.status === "pending_review" ? (
            <button type="button">Approve</button>
          ) : null
        }
      />,
    );
    expect(screen.getAllByText(/INFERENCE \(tentative\)/)).toHaveLength(2);
    expect(screen.getAllByText(/2 evidence/)).toHaveLength(2);
    expect(screen.getByText(/retracted/)).toBeInTheDocument();
    expect(screen.getByText("Approve")).toBeInTheDocument();
  });
});
