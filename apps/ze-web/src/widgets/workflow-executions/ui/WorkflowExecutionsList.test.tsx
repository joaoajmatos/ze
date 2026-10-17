import type { WorkflowExecutionResponse } from "@myguyze/ze-client";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkflowExecutionsList } from "./WorkflowExecutionsList";

function execution(overrides: Partial<WorkflowExecutionResponse>): WorkflowExecutionResponse {
  return {
    id: "ex-1",
    workflow_id: "wf-1",
    status: "completed",
    step_results: [],
    steps_snapshot: [],
    error: null,
    failure_summary: null,
    summary: null,
    started_at: "2026-10-17T10:00:00Z",
    completed_at: "2026-10-17T10:00:05Z",
    created_at: "2026-10-17T10:00:00Z",
    ...overrides,
  };
}

describe("WorkflowExecutionsList", () => {
  it("shows the plain failure line and never the raw error", () => {
    render(
      <WorkflowExecutionsList
        executions={[
          execution({
            status: "failed",
            error: "TimeoutError: Traceback (most recent call last)",
            failure_summary: "Step 2 of 4, “Check the inbox”, failed: it ran out of time.",
          }),
        ]}
        onSelect={() => {}}
      />,
    );
    expect(
      screen.getByText("Step 2 of 4, “Check the inbox”, failed: it ran out of time."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
  });

  it("shows no failure line for a completed run", () => {
    render(<WorkflowExecutionsList executions={[execution({})]} onSelect={() => {}} />);
    expect(screen.queryByText(/failed:/)).not.toBeInTheDocument();
  });
});
