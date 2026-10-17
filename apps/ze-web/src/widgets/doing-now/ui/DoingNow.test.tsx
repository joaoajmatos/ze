import type { GoalListItem, WorkflowExecutionResponse, WorkflowResponse } from "@myguyze/ze-client";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DoingNow } from "./DoingNow";

const now = new Date("2026-10-17T12:00:00Z");
const goal = (id: string, extra: Partial<GoalListItem> = {}) => ({ id, title: `Goal ${id}`, status: "active", milestones_done: 1, milestones_total: 4, next_milestone: "Draft outline", gate_id: null, stuck_since: null, ...extra }) as GoalListItem;
const wf = (id: string, extra: Partial<WorkflowResponse> = {}) => ({ id, name: `Flow ${id}`, enabled: true, next_run_at: "2026-10-18T07:30:00Z", ...extra }) as WorkflowResponse;
const ex = (id: string, status: string, hoursAgo: number, extra: Partial<WorkflowExecutionResponse> = {}) =>
  ({ id, status, started_at: new Date(now.getTime() - hoursAgo * 3_600_000).toISOString(), created_at: new Date(now.getTime() - hoursAgo * 3_600_000).toISOString(), failure_summary: null, error: "Traceback (most recent call last): boom", ...extra }) as WorkflowExecutionResponse;

function setup(over: Partial<Parameters<typeof DoingNow>[0]> = {}) {
  return render(<DoingNow goals={[]} workflows={[]} executions={{}} loading={false} error={false} now={now} {...over} />);
}

describe("DoingNow", () => {
  it("shows active goals with progress and the next milestone", () => {
    setup({ goals: [goal("a"), goal("done", { status: "completed" })] });
    expect(screen.getByText("Goal a")).toBeTruthy();
    expect(screen.getByText("1/4")).toBeTruthy();
    expect(screen.getByText("Next: Draft outline")).toBeTruthy();
    expect(screen.queryByText("Goal done")).toBeNull();
  });

  it("says stuck since for a stuck goal and waiting for a gate", () => {
    setup({ goals: [goal("s", { stuck_since: "2026-10-12T12:00:00Z" }), goal("g", { gate_id: "x" })] });
    expect(screen.getByText("Stuck since 5 days ago")).toBeTruthy();
    expect(screen.getByText("Waiting on your OK")).toBeTruthy();
  });

  it("shows the next run and the week's ok and failed counts", () => {
    setup({
      workflows: [wf("a"), wf("b", { next_run_at: "2026-10-19T07:30:00Z" }), wf("off", { enabled: false, next_run_at: "2026-10-17T13:00:00Z" })],
      executions: { a: [ex("1", "completed", 2), ex("2", "completed", 30), ex("3", "failed", 50)], b: [ex("4", "completed", 24 * 9)] },
    });
    expect(screen.getByText("Flow a")).toBeTruthy();
    expect(screen.getByText("2 ok · 1 failed")).toBeTruthy();
    expect(screen.queryByText("Flow off")).toBeNull();
  });

  it("lists a running execution", () => {
    setup({ workflows: [wf("a")], executions: { a: [ex("1", "running", 0)] } });
    expect(screen.getByText("running")).toBeTruthy();
  });

  it("shows failure_summary for a failed latest run and never the raw error", () => {
    const { container } = setup({
      workflows: [wf("a")],
      executions: { a: [ex("1", "failed", 1, { failure_summary: "Step 2 (fetch) failed: the browser tool errored." })] },
    });
    expect(screen.getByText("Step 2 (fetch) failed: the browser tool errored.")).toBeTruthy();
    expect(container.textContent).not.toContain("Traceback");
  });

  it("renders the error state", () => {
    setup({ error: true });
    expect(screen.getByRole("alert").textContent).toContain("Couldn't read");
  });
});
