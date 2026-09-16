import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewProcedureCandidate } from "./ReviewProcedureCandidate";

const { useReviewProcedureMutation } = vi.hoisted(() => ({
  useReviewProcedureMutation: vi.fn(),
}));

vi.mock("@/entities/procedure", () => ({
  useReviewProcedureMutation,
}));

const pending = {
  id: "cand-1",
  source_kind: "goal",
  provenance: "synthesized",
  name: "Weekly review",
  trigger: "friday",
  preconditions: [],
  steps: ["read notes"],
  success_criteria: ["plan written"],
  limits: [],
  evidence_refs: [{ kind: "goal", id: "goal-1" }],
  learning_refs: [],
  status: "pending",
  submitted_at: new Date().toISOString(),
  resolved_at: null,
};

function setup(mutate = vi.fn()) {
  useReviewProcedureMutation.mockReturnValue({ mutate, isPending: false });
  return mutate;
}

describe("ReviewProcedureCandidate", () => {
  it("offers review actions on pending candidates", () => {
    setup();
    render(<ReviewProcedureCandidate candidate={pending} />);
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
  });

  it("calls approve with the candidate id", () => {
    const mutate = setup();
    render(<ReviewProcedureCandidate candidate={pending} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(mutate).toHaveBeenCalledWith({
      candidateId: "cand-1",
      decision: "approve",
      reason: "approved from memory review",
    });
  });
});
