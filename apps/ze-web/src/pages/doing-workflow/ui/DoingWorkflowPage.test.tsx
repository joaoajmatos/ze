import type { WorkflowDetailResponse, WorkflowExecutionResponse, WorkflowRevisionResponse } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  detail: { data: undefined as unknown, isLoading: false, isError: false, refetch: vi.fn() },
  execs: { data: [] as unknown[], isLoading: false, isError: false },
  revs: { data: [] as unknown[], isLoading: false, isError: false },
  live: { data: null as unknown },
  trigger: { mutate: vi.fn(), isPending: false, isError: false },
  cancel: { mutate: vi.fn(), isPending: false, isError: false },
  chatAbout: vi.fn(),
  select: vi.fn(),
  highlight: vi.fn(),
  publisher: vi.fn(),
}));
vi.mock("@/entities/workflow", async (orig) => ({
  ...(await orig<object>()),
  useWorkflowDetailQuery: () => m.detail,
  useWorkflowExecutionsQuery: () => m.execs,
  useWorkflowRevisionsQuery: () => m.revs,
  useLiveExecutionQuery: () => m.live,
  useTriggerWorkflowMutation: () => m.trigger,
  useCancelExecutionMutation: () => m.cancel,
}));
vi.mock("@/features/ask-bar", () => ({ useChatAbout: () => m.chatAbout }));
vi.mock("@/entities/screen-context", () => ({ useScreenPublisher: (...a: unknown[]) => m.publisher(...a) }));
vi.mock("@/shared/lib", async (orig) => ({ ...(await orig<object>()), useSetBreadcrumbTitle: () => {} }));
vi.mock("@/entities/session", () => ({ useSession: { getState: () => ({ selectSession: m.select, setHighlightMessage: m.highlight }) } }));
vi.mock("@/widgets/workflow-graph", () => ({
  WorkflowGraph: ({ steps }: { steps: { task: string }[] }) => <div data-testid="graph">{steps.map((s) => s.task).join(", ")}</div>,
}));

import { DoingWorkflowPage } from "./DoingWorkflowPage";

const wf: WorkflowDetailResponse = {
  id: "wf-1", name: "Daily check", description: "Checks inbox", schedule: null, enabled: true, last_run_at: null, next_run_at: null,
  created_at: "2026-07-10T00:00:00Z",
  steps: [{ id: "s0", task: "Current step", agent_hint: null, verify: null, branches: [], default_next: null, on_failure: "fail" }],
};
const exec = (o: Partial<WorkflowExecutionResponse> = {}): WorkflowExecutionResponse => ({
  id: "e1", workflow_id: "wf-1", status: "completed", step_results: [], steps_snapshot: [], error: null, failure_summary: null, summary: null,
  started_at: "2026-07-09T12:00:00Z", completed_at: "2026-07-09T12:05:00Z", created_at: "2026-07-09T12:00:00Z", ...o,
});
const rev = (o: Partial<WorkflowRevisionResponse> = {}): WorkflowRevisionResponse =>
  ({ id: "r1", workflow_id: "wf-1", revision_number: 1, change_type: "created", steps_before: [], steps_after: [], summary: "Created with 1 step",
    actor_source: "agent", actor_session_id: "sess-1", actor_user_message_id: "msg-1", created_at: "2026-07-09T11:00:00Z", ...o }) as WorkflowRevisionResponse;
const view = (path = "/doing/workflows/wf-1") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/doing/workflows/:workflowId" element={<DoingWorkflowPage />} />
        <Route path="/ask/:id" element={<div>ask page</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe("DoingWorkflowPage", () => {
  beforeEach(() => {
    m.detail = { data: wf, isLoading: false, isError: false, refetch: vi.fn() };
    m.execs = { data: [], isLoading: false, isError: false };
    m.revs = { data: [], isLoading: false, isError: false };
    m.live = { data: null };
    m.trigger = { mutate: vi.fn(), isPending: false, isError: false };
    m.cancel = { mutate: vi.fn(), isPending: false, isError: false };
    m.chatAbout.mockReset();
    m.select.mockReset();
    m.highlight.mockReset();
  });

  it("shows the flowchart with the current steps and no definition banner", () => {
    const { container } = view();
    expect(screen.getByTestId("graph")).toHaveTextContent("Current step");
    expect(container.textContent).not.toMatch(/Current definition/i);
  });

  it("says Never run when there are no executions", () => {
    view();
    expect(screen.getByText("Never run.")).toBeInTheDocument();
  });

  it("lists executions; a failed one is coral with failure_summary and never error", () => {
    m.execs.data = [exec({ id: "e2", status: "failed", failure_summary: "Step 1 could not reach mail", error: "Traceback (most recent call last)" }), exec()];
    const { container } = view();
    expect(screen.getByText("Step 1 could not reach mail")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Traceback/);
    expect(container.querySelectorAll("li.row.hot")).toHaveLength(1);
  });

  it("selecting a run shows its snapshot in the graph and the summary", () => {
    m.execs.data = [exec({ summary: "All good", steps_snapshot: [{ id: "s0", task: "Old step", agent_hint: null, verify: null, branches: [], default_next: null, on_failure: "fail" }] })];
    view();
    fireEvent.click(screen.getByText("Completed"));
    expect(screen.getByTestId("graph")).toHaveTextContent("Old step");
    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("opens the run named by ?execution=", () => {
    m.execs.data = [exec({ id: "x9", summary: "From the link" })];
    view("/doing/workflows/wf-1?execution=x9");
    expect(screen.getByText("From the link")).toBeInTheDocument();
  });

  it("shows the live execution while it runs", () => {
    m.live = { data: exec({ status: "running", completed_at: null }) };
    view();
    expect(screen.getByText("Running…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run now" })).toBeDisabled();
  });

  it("Run now triggers and Cancel appears for a running execution", () => {
    view();
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));
    expect(m.trigger.mutate).toHaveBeenCalledWith("wf-1", expect.anything());
  });

  it("Cancel cancels the running execution", () => {
    m.live = { data: exec({ id: "live1", status: "running", completed_at: null }) };
    view();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(m.cancel.mutate).toHaveBeenCalledWith({ workflowId: "wf-1", executionId: "live1" });
  });

  it("Chat about this run opens a chat on the execution with its workflow as parent", () => {
    m.execs.data = [exec()];
    view();
    fireEvent.click(screen.getByText("Completed"));
    fireEvent.click(screen.getByRole("button", { name: "Chat about this run" }));
    expect(m.chatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "workflow_execution", id: "e1", parent_id: "wf-1" }), expect.anything());
  });

  it("lists revisions with a diff summary and View conversation only for agent edits", () => {
    m.revs.data = [rev(), rev({ id: "r2", revision_number: 2, actor_source: "api", actor_session_id: null, actor_user_message_id: null, summary: "Step s0: on_failure fail → continue" })];
    view();
    expect(screen.getByText("Step s0: on_failure fail → continue")).toBeInTheDocument();
    expect(screen.getAllByText("View conversation")).toHaveLength(1);
  });

  it("View conversation selects the session and goes to Ask", () => {
    m.revs.data = [rev()];
    view();
    fireEvent.click(screen.getByText("View conversation"));
    expect(m.select).toHaveBeenCalledWith("sess-1");
    expect(m.highlight).toHaveBeenCalledWith("msg-1");
    expect(screen.getByText("ask page")).toBeInTheDocument();
  });

  it("expands a revision to show before and after", () => {
    m.revs.data = [rev({ steps_before: [{ id: "s0", task: "Old task", agent_hint: null, verify: null, branches: [], default_next: null, on_failure: "fail" }], steps_after: [{ id: "s0", task: "New task", agent_hint: null, verify: null, branches: [], default_next: null, on_failure: "fail" }] })];
    view();
    fireEvent.click(screen.getByText("Created with 1 step"));
    expect(screen.getByText("Old task")).toBeInTheDocument();
    expect(screen.getByText("New task")).toBeInTheDocument();
  });

  it("has no empty line while loading or on error", () => {
    m.execs = { data: [], isLoading: true, isError: false };
    m.revs = { data: [], isLoading: false, isError: true };
    view();
    expect(screen.queryByText("Never run.")).toBeNull();
    expect(screen.queryByText(/No changes recorded/)).toBeNull();
    expect(screen.getByText("Couldn't read the change history.")).toBeInTheDocument();
  });

  it("not found shows an error with Retry", () => {
    m.detail = { data: undefined, isLoading: false, isError: true, refetch: vi.fn() };
    view();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(m.detail.refetch).toHaveBeenCalled();
  });
});
