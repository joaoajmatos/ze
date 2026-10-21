import type { GoalDetailResponse } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  detail: { data: undefined as unknown, isLoading: false, isError: false, refetch: vi.fn() },
  traces: { data: [] as unknown[], isLoading: false, isError: false },
  loops: { data: [] as unknown[], isLoading: false, isError: false },
  reminders: { data: [] as unknown[], isError: false },
  start: { mutate: vi.fn(), isPending: false, isError: false },
  gate: {} as Record<string, unknown>,
  chatAbout: vi.fn(),
  startGoalCalled: vi.fn(),
  publisher: vi.fn(),
}));
vi.mock("@/entities/goal", async (orig) => ({
  ...(await orig<object>()),
  useGoalDetailQuery: () => m.detail,
  useGoalTracesQuery: () => m.traces,
  useStartGoalMutation: () => m.start,
}));
vi.mock("@/entities/loop", () => ({ useLoopsQuery: () => m.loops }));
vi.mock("@/entities/reminder", () => ({ useRemindersQuery: () => m.reminders }));
vi.mock("@/entities/screen-context", () => ({ useScreenPublisher: (...a: unknown[]) => m.publisher(...a) }));
vi.mock("@/features/answer-gate", () => ({ useAnswerGate: () => m.gate }));
vi.mock("@/features/ask-bar", () => ({ useChatAbout: () => m.chatAbout }));
vi.mock("@/features/review-goal-learning", () => ({ ReviewGoalLearning: () => <span data-testid="review" /> }));
vi.mock("@/widgets/milestone-field", () => ({ MilestoneField: () => <div data-testid="field" /> }));
vi.mock("@/shared/api", () => ({ useWsStore: (sel: (s: { isConnected: boolean }) => unknown) => sel({ isConnected: true }) }));
vi.mock("@/shared/lib", async (orig) => ({ ...(await orig<object>()), useSetBreadcrumbTitle: () => {} }));

import { DoingGoalPage } from "./DoingGoalPage";

const detail = (o: Partial<GoalDetailResponse> = {}): GoalDetailResponse => ({
  id: "g1", title: "Learn Rust", objective: "Ship a CLI", success_condition: "", status: "active", type: "one_off", time_horizon: "multi_week",
  learnings_summary: null, retrospective_text: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-10T00:00:00Z",
  milestones: [], gates: [], learnings: [], ...o,
});
const gateApi = () => ({ stateOf: () => "idle", errorOf: () => null, proceed: vi.fn(() => true), stop: vi.fn(() => true), redirect: vi.fn(() => true) });
const view = () =>
  render(
    <MemoryRouter initialEntries={["/doing/goals/g1"]}>
      <Routes>
        <Route path="/doing/goals/:goalId" element={<DoingGoalPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("DoingGoalPage", () => {
  beforeEach(() => {
    m.detail = { data: detail(), isLoading: false, isError: false, refetch: vi.fn() };
    m.traces = { data: [], isLoading: false, isError: false };
    m.loops = { data: [], isLoading: false, isError: false };
    m.reminders = { data: [], isError: false };
    m.start.mutate.mockReset();
    m.gate = gateApi();
    m.chatAbout.mockReset();
  });

  it("renders an open gate first with the shared actions", () => {
    m.detail.data = detail({ gates: [{ id: "gt1", title: "Approve plan", status: "awaiting_approval", after_sequence: 1, context_summary: null, plan_summary: "Three steps", user_feedback: null, fired_at: "2026-10-12T09:00:00Z", resolved_at: null }] });
    const { container } = view();
    const first = container.querySelector(".mod");
    expect(first).toHaveTextContent("Approve plan");
    fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
    expect((m.gate.proceed as ReturnType<typeof vi.fn>)).toHaveBeenCalledWith("gt1");
    fireEvent.click(screen.getByRole("button", { name: "Redirect" }));
    expect(m.chatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal_gate", id: "gt1", parent_id: "g1", label: expect.any(String) }), null);
    expect(m.start.mutate).not.toHaveBeenCalled();
  });

  it("shows Start for a planning goal", () => {
    m.detail.data = detail({ status: "planning" });
    view();
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(m.start.mutate).toHaveBeenCalledWith("g1");
  });

  it("says status, type and time horizon in words", () => {
    const { container } = view();
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("One off")).toBeInTheDocument();
    expect(screen.getByText("Multi week")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/one_off|multi_week/);
    expect(screen.getByTestId("field")).toBeInTheDocument();
  });

  it("shows retrospective and learnings summary when present", () => {
    m.detail.data = detail({ retrospective_text: "It went well.", learnings_summary: "Small steps win." });
    view();
    expect(screen.getByText("It went well.")).toBeInTheDocument();
    expect(screen.getByText("Small steps win.")).toBeInTheDocument();
  });

  it("lists learnings with evidence and a review slot", () => {
    m.detail.data = detail({ learnings: [{ id: "l1", content: "Tests first", claim_kind: "inference", provenance: "x", confidence: 0.6, status: "pending_review", evidence_count: 2, promotion_state: null, review_needed: true, created_at: null }] });
    view();
    expect(screen.getByText("Tests first")).toBeInTheDocument();
    expect(screen.getByText("Inference (tentative)")).toBeInTheDocument();
    expect(screen.getByText(/2 pieces of evidence/)).toBeInTheDocument();
    expect(screen.getByTestId("review")).toBeInTheDocument();
  });

  it("lists traces as a readout with no Show tool calls toggle", () => {
    m.traces.data = [{ id: "t1", tool_name: "web_search", success: true, duration_ms: 120, error: null }, { id: "t2", tool_name: "send_email", success: false, duration_ms: 5, error: "SMTP refused" }];
    view();
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(screen.getByText("Worked")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("SMTP refused").tagName).toBe("PRE");
    expect(screen.getByText("SMTP refused").closest("details")).not.toBeNull();
    expect(screen.queryByText(/Show tool calls/i)).toBeNull();
  });

  it("loads all loops and filters by goal (single user, no per-goal route)", () => {
    m.loops.data = [{ id: "a", title: "Mine", state: "active", goal_id: "g1", reminder_id: null }, { id: "b", title: "Other", state: "active", goal_id: "g2", reminder_id: null }];
    view();
    expect(screen.getByText("Mine")).toBeInTheDocument();
    expect(screen.queryByText("Other")).toBeNull();
  });

  it("shows a linked loop's reminder with due time and status word, nothing when missing", () => {
    m.loops.data = [{ id: "a", title: "Call the bank", state: "active", goal_id: "g1", reminder_id: "r1" }, { id: "b", title: "No reminder here", state: "active", goal_id: "g1", reminder_id: "gone" }];
    m.reminders.data = [{ id: "r1", label: "Bank call", fire_at: "2026-10-20T09:00:00Z", sent_at: null, status: "overdue" }];
    view();
    expect(screen.getByText(/Reminder · Bank call · overdue/)).toBeInTheDocument();
    expect(screen.getAllByText(/Reminder ·/)).toHaveLength(1);
  });

  it("does not claim emptiness while loading or on error", () => {
    m.loops = { data: [], isLoading: true, isError: false };
    m.traces = { data: [], isLoading: false, isError: true };
    view();
    expect(screen.queryByText(/Nothing open is linked/)).toBeNull();
    expect(screen.queryByText(/No tool calls recorded/)).toBeNull();
    expect(screen.getByText("Couldn't read what it did.")).toBeInTheDocument();
  });

  it("not found shows an error line with Retry", () => {
    m.detail = { data: undefined, isLoading: false, isError: true, refetch: vi.fn() };
    view();
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load this goal.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(m.detail.refetch).toHaveBeenCalled();
  });

  it("publishes the goal as the screen subject", () => {
    view();
    expect(m.publisher).toHaveBeenCalledWith(expect.objectContaining({ subject: [expect.objectContaining({ kind: "goal", id: "g1" })] }));
  });

  it("says when the trace list is cut at the limit", () => {
    m.traces.data = Array.from({ length: 100 }, (_, n) => ({ id: `t${n}`, tool_name: "x", success: true, duration_ms: 1, error: null }));
    view();
    expect(screen.getByText("Showing the first 100 tool calls.")).toBeInTheDocument();
  });

  it("says so when the reminders could not be read", () => {
    m.loops.data = [{ id: "a", title: "Call", state: "active", goal_id: "g1", reminder_id: "r1" }];
    m.reminders = { data: [], isError: true };
    view();
    expect(screen.getByText("Couldn't read reminders.")).toBeInTheDocument();
  });

  it("says the checkpoint is unavailable when the goal awaits a gate but none is open", () => {
    m.detail.data = detail({ status: "awaiting_gate", gates: [] });
    view();
    expect(screen.getByText(/the checkpoint isn't available/)).toBeInTheDocument();
  });
});
