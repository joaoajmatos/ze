import type { GoalListItem, HeldWriteOut } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AnswerGate } from "@/features/answer-gate";

const start = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false, variables: undefined as string | undefined }));
vi.mock("@/entities/goal", () => ({ useStartGoalMutation: () => start }));
vi.mock("@/features/respond-to-confirmation", () => ({
  HeldWriteCard: ({ held }: { held: HeldWriteOut }) => <div data-testid="held">{held.source_name}</div>,
}));

import { DoingNeedsYou } from "./DoingNeedsYou";

const goal = (o: Partial<GoalListItem>): GoalListItem => ({
  id: "g1", title: "Learn Rust", objective: "", status: "active", created_at: "2026-10-01T00:00:00Z",
  milestones_done: 0, milestones_total: 0, next_milestone: null, gate_id: null, gate_title: null,
  gate_open_since: null, last_progress_at: null, stuck_since: null, ...o,
});
const held = { request_id: "h1", source: "workflow", source_name: "Weekly digest", items: [] } as unknown as HeldWriteOut;

function fakeGate(over: Partial<AnswerGate> = {}): AnswerGate {
  return {
    offline: false, answer: vi.fn(), proceed: vi.fn(() => true), stop: vi.fn(() => true), redirect: vi.fn(() => true),
    pause: vi.fn(), redirectStuck: vi.fn(), abandon: vi.fn(), abandonArmed: () => false, disarmAbandon: vi.fn(),
    stateOf: () => "idle", errorOf: () => null, ...over,
  } as AnswerGate;
}
const props = { goals: [], held: [], loading: false, error: false, now: new Date("2026-10-18T12:00:00Z"), offline: false };

describe("DoingNeedsYou", () => {
  it("says nothing needs you when empty", () => {
    render(<DoingNeedsYou {...props} gate={fakeGate()} />);
    expect(screen.getByText("Nothing needs you.")).toBeInTheDocument();
  });

  it("does not show an empty state while loading or on error", () => {
    const { rerender } = render(<DoingNeedsYou {...props} loading gate={fakeGate()} />);
    expect(screen.queryByText("Nothing needs you.")).toBeNull();
    rerender(<DoingNeedsYou {...props} error gate={fakeGate()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't read");
    expect(screen.queryByText("Nothing needs you.")).toBeNull();
  });

  it("starts a planning goal", () => {
    render(<DoingNeedsYou {...props} goals={[goal({ status: "planning" })]} gate={fakeGate()} />);
    expect(screen.getByText("plan ready")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(start.mutate).toHaveBeenCalledWith("g1");
  });

  it("answers a gate through the shared sender, Redirect opening the chat on the goal gate", () => {
    const gate = fakeGate();
    const onChatAbout = vi.fn();
    render(<DoingNeedsYou {...props} goals={[goal({ status: "awaiting_gate", gate_id: "gt1", gate_title: "Approve plan", gate_open_since: "2026-10-18T10:00:00Z" })]} gate={gate} onChatAbout={onChatAbout} />);
    expect(screen.getByText(/Checkpoint · Learn Rust · waiting/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    fireEvent.click(screen.getByRole("button", { name: "Redirect" }));
    expect(gate.proceed).toHaveBeenCalledWith("gt1");
    expect(gate.stop).toHaveBeenCalledWith("gt1");
    expect(gate.redirect).toHaveBeenCalledWith("gt1");
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal_gate", id: "gt1", parent_id: "g1", label: expect.any(String) }), null);
  });

  it("disables gate buttons in flight and shows the error line", () => {
    const gate = fakeGate({ stateOf: () => "in_flight", errorOf: () => "Ze hasn't answered yet." });
    render(<DoingNeedsYou {...props} goals={[goal({ gate_id: "gt1" })]} gate={gate} />);
    expect(screen.getByRole("button", { name: "Proceed" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("hasn't answered");
  });

  it("renders held writes with HeldWriteCard", () => {
    render(<DoingNeedsYou {...props} held={[held]} gate={fakeGate()} />);
    expect(screen.getByTestId("held")).toHaveTextContent("Weekly digest");
  });

  it("is cream and never coral", () => {
    const { container } = render(<DoingNeedsYou {...props} goals={[goal({ status: "planning" })]} held={[held]} gate={fakeGate()} />);
    expect(container.querySelector(".mod.cream")).not.toBeNull();
    expect(container.querySelector(".mod.hot, .row.hot")).toBeNull();
  });

  it("disables actions offline", () => {
    render(<DoingNeedsYou {...props} offline goals={[goal({ status: "planning" })]} gate={fakeGate()} />);
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
  });
  it("Chat about this on a gate passes goal_gate with its goal as parent, and on a held write a held_write ref", () => {
    const onChatAbout = vi.fn();
    render(<DoingNeedsYou {...props} goals={[goal({ gate_id: "gt1", gate_title: "Approve" })]} held={[held]} gate={fakeGate()} onChatAbout={onChatAbout} />);
    fireEvent.click(screen.getByRole("button", { name: "Chat about Approve" }));
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal_gate", id: "gt1", parent_id: "g1", label: expect.any(String) }), expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Chat about Weekly digest" }));
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "held_write", id: "h1", label: expect.any(String) }), expect.anything());
  });
});
