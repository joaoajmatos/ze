import type { GoalListItem } from "@myguyze/ze-client";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { AnswerGate } from "@/features/answer-gate";
import { GoalsBoard } from "./GoalsBoard";

const goal = (o: Partial<GoalListItem>): GoalListItem => ({
  id: "g1", title: "Learn Rust", objective: "", status: "active", created_at: "2026-10-01T00:00:00Z",
  milestones_done: 1, milestones_total: 4, next_milestone: "Ownership", gate_id: null, gate_title: null,
  gate_open_since: null, last_progress_at: "2026-10-10T00:00:00Z", stuck_since: null, ...o,
});
function fakeGate(over: Partial<AnswerGate> = {}): AnswerGate {
  return {
    offline: false, answer: vi.fn(), proceed: vi.fn(), stop: vi.fn(), redirect: vi.fn(),
    pause: vi.fn(() => true), redirectStuck: vi.fn(() => true), abandon: vi.fn(), abandonArmed: () => false,
    disarmAbandon: vi.fn(), stateOf: () => "idle", errorOf: () => null, ...over,
  } as AnswerGate;
}
const base = { loading: false, error: false, offline: false };
const view = (goals: GoalListItem[], gate = fakeGate(), extra: Partial<React.ComponentProps<typeof GoalsBoard>> = {}) =>
  render(
    <MemoryRouter>
      <GoalsBoard {...base} goals={goals} gate={gate} {...extra} />
    </MemoryRouter>,
  );

describe("GoalsBoard", () => {
  it("shows meter, next milestone, age and a link to the goal", () => {
    view([goal({})]);
    expect(screen.getByRole("link", { name: "Learn Rust" })).toHaveAttribute("href", "/doing/goals/g1");
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "25");
    expect(screen.getByText("1/4 milestones")).toBeInTheDocument();
    expect(screen.getByText(/Next: Ownership/)).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("orders stuck first, then gate open, and no other row is coral", () => {
    const { container } = view([
      goal({ id: "a", title: "Plain" }),
      goal({ id: "b", title: "Gate", status: "awaiting_gate", gate_id: "x", gate_open_since: "2026-10-12T00:00:00Z" }),
      goal({ id: "c", title: "Stuck", stuck_since: "2026-10-05T00:00:00Z" }),
    ]);
    const titles = [...container.querySelectorAll("li.row .t")].map((e) => e.textContent);
    expect(titles).toEqual(["Stuck", "Gate", "Plain"]);
    expect(container.querySelectorAll("li.row.hot")).toHaveLength(1);
    expect(screen.getByText(/gate open since/)).toBeInTheDocument();
  });

  it("gives a stuck goal Redirect, Pause and Abandon through the gate sender", () => {
    const gate = fakeGate();
    const onChatAbout = vi.fn();
    view([goal({ stuck_since: "2026-10-05T00:00:00Z" })], gate, { onChatAbout });
    expect(screen.getByText(/stuck since/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Redirect" }));
    expect(gate.redirectStuck).toHaveBeenCalledWith("g1");
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal", id: "g1", label: expect.any(String) }), null);
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(gate.pause).toHaveBeenCalledWith("g1");
    fireEvent.click(screen.getByRole("button", { name: "Abandon" }));
    expect(gate.abandon).toHaveBeenCalledWith("g1");
  });

  it("asks once before abandoning", () => {
    const gate = fakeGate({ abandonArmed: () => true });
    view([goal({ stuck_since: "2026-10-05T00:00:00Z" })], gate);
    fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
    expect(gate.disarmAbandon).toHaveBeenCalledWith("g1");
    fireEvent.click(screen.getByRole("button", { name: "Yes, abandon" }));
    expect(gate.abandon).toHaveBeenCalledWith("g1");
  });

  it("puts a paused goal after live ones with Resume opening the chat", () => {
    const onChatAbout = vi.fn();
    const { container } = view([goal({ id: "p", title: "Paused one", status: "paused" }), goal({ id: "a", title: "Live" })], fakeGate(), { onChatAbout });
    expect([...container.querySelectorAll("li.row .t")].map((e) => e.textContent)).toEqual(["Live", "Paused one"]);
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal", id: "p", label: expect.any(String) }), null);
    expect(screen.getByText("Paused", { selector: ".lbl" })).toBeInTheDocument();
  });

  it("collapses finished goals under Finished (n)", () => {
    const { container } = view([goal({ id: "d", status: "completed" }), goal({ id: "e", status: "abandoned" })]);
    const details = container.querySelector("details.doing-finished")!;
    expect(details).not.toHaveAttribute("open");
    expect(within(details as HTMLElement).getByText("Finished (2)")).toBeInTheDocument();
  });

  it("shows no raw status", () => {
    const { container } = view([goal({ status: "awaiting_gate" })]);
    expect(container.textContent).not.toMatch(/awaiting_gate/);
  });

  it("is not empty-looking while loading or on error", () => {
    const { rerender } = view([], fakeGate(), { loading: true });
    expect(screen.queryByText(/No goals yet/)).toBeNull();
    rerender(
      <MemoryRouter>
        <GoalsBoard {...base} error goals={[]} gate={fakeGate()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(/No goals yet/)).toBeNull();
  });
  it("Chat about this on a goal row passes the goal ref", () => {
    const onChatAbout = vi.fn();
    view([goal({})], fakeGate(), { onChatAbout });
    fireEvent.click(screen.getByRole("button", { name: "Chat about Learn Rust" }));
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "goal", id: "g1", label: expect.any(String) }), expect.anything());
  });

  it("says the checkpoint is unavailable for a goal awaiting a gate with no gate id", () => {
    view([goal({ status: "awaiting_gate" })]);
    expect(screen.getByText(/checkpoint that isn't available/)).toBeInTheDocument();
  });

  it("does not say the checkpoint is unavailable when the goal has a gate id", () => {
    view([goal({ status: "awaiting_gate", gate_id: "x" })]);
    expect(screen.queryByText(/isn't available/)).toBeNull();
  });
});
