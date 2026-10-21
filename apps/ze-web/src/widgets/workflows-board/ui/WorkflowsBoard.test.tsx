import type { WorkflowExecutionResponse, WorkflowResponse } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const trigger = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false, variables: undefined as string | undefined }));
vi.mock("@/entities/workflow", async (orig) => ({ ...(await orig<object>()), useTriggerWorkflowMutation: () => trigger }));

import { WorkflowsBoard } from "./WorkflowsBoard";

const wf = (o: Partial<WorkflowResponse> = {}): WorkflowResponse => ({
  id: "w1", name: "Weekly digest", description: "", schedule: "0 8 * * 1", enabled: true,
  last_run_at: "2026-10-12T08:00:00Z", next_run_at: "2026-10-19T08:00:00Z", created_at: "2026-09-01T00:00:00Z", ...o,
});
const ex = (o: Partial<WorkflowExecutionResponse>): WorkflowExecutionResponse => ({
  id: "e1", workflow_id: "w1", status: "completed", step_results: [], error: null, failure_summary: null, summary: null,
  started_at: null, completed_at: null, created_at: "2026-10-12T08:00:00Z", ...o,
});
const now = new Date("2026-10-18T12:00:00Z");
const base = { loading: false, error: false, offline: false, now };
const view = (props: Partial<React.ComponentProps<typeof WorkflowsBoard>>) =>
  render(
    <MemoryRouter>
      <WorkflowsBoard {...base} workflows={[wf()]} executions={{}} {...props} />
    </MemoryRouter>,
  );

describe("WorkflowsBoard", () => {
  beforeEach(() => trigger.mutate.mockReset());

  it("shows the schedule in words and Never run", () => {
    view({ executions: { w1: [] } });
    expect(screen.getByText(/At 08:00 AM, only on Monday/)).toBeInTheDocument();
    expect(screen.getByText("Never run")).toBeInTheDocument();
  });

  it("shows a failed last result in coral with failure_summary, not error", () => {
    const { container } = view({ executions: { w1: [ex({ status: "failed", failure_summary: "Step 2 could not reach the calendar", error: "Traceback" })] } });
    expect(screen.getByText(/Last run failed: Step 2 could not reach the calendar/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Traceback/);
    expect(container.querySelector("li.row.hot")).not.toBeNull();
  });

  it("shows Running and disables Run now", () => {
    view({ executions: { w1: [ex({ status: "running" })] } });
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run now" })).toBeDisabled();
  });

  it("Run now triggers the workflow", () => {
    view({});
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));
    expect(trigger.mutate).toHaveBeenCalledWith("w1");
  });

  it("Open goes to the workflow page", () => {
    view({});
    expect(screen.getAllByRole("link", { name: /Open|Weekly digest/ }).every((l) => l.getAttribute("href") === "/doing/workflows/w1")).toBe(true);
  });

  it("no empty state while loading or on error", () => {
    const { unmount } = view({ workflows: [], loading: true });
    expect(screen.queryByText(/No workflows yet/)).toBeNull();
    unmount();
    view({ workflows: [], error: true });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't read");
    expect(screen.queryByText(/No workflows yet/)).toBeNull();
  });
  it("Chat about this on a workflow row passes the workflow ref", () => {
    const onChatAbout = vi.fn();
    view({ onChatAbout });
    fireEvent.click(screen.getByRole("button", { name: "Chat about Weekly digest" }));
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "workflow", id: "w1", label: expect.any(String) }), expect.anything());
  });

  it("shows a dash, not Never run, for a workflow whose executions were not fetched", () => {
    view({ executions: {} });
    expect(screen.queryByText("Never run")).toBeNull();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("says cancelled and held honestly, never fine", () => {
    const { unmount } = view({ executions: { w1: [ex({ status: "cancelled" })] } });
    expect(screen.getByText("Last run was cancelled")).toBeInTheDocument();
    unmount();
    view({ executions: { w1: [ex({ status: "held" })] } });
    expect(screen.getByText("Waiting on a write you have not approved")).toBeInTheDocument();
    expect(screen.queryByText(/went fine/)).toBeNull();
  });

});
