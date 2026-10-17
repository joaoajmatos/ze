import type { GoalListItem, LoopListItem, WorkflowResponse } from "@myguyze/ze-client";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Touched } from "./Touched";

const now = new Date("2026-10-17T12:00:00Z");
const daysAgo = (n: number) => new Date(now.getTime() - n * 86_400_000).toISOString();
const loop = (id: string, state: string, n: number) => ({ id, title: `Loop ${id}`, state, updated_at: daysAgo(n) }) as LoopListItem;

function setup(over: Partial<Parameters<typeof Touched>[0]> = {}) {
  return render(<Touched loops={[]} closedLoops={[]} goals={[]} workflows={[]} loading={false} error={false} now={now} {...over} />);
}

describe("Touched", () => {
  it("applies the seven-day window to loops, goals and workflows", () => {
    setup({
      loops: [loop("recent", "active", 2), loop("old", "active", 9)],
      goals: [{ id: "g", title: "Goal g", status: "active", last_progress_at: daysAgo(1) } as GoalListItem, { id: "g2", title: "Goal old", status: "active", last_progress_at: daysAgo(20) } as GoalListItem],
      workflows: [{ id: "w", name: "Flow w", last_run_at: daysAgo(3) } as WorkflowResponse, { id: "w2", name: "Flow stale", last_run_at: null } as WorkflowResponse],
    });
    expect(screen.getByText("Loop recent")).toBeTruthy();
    expect(screen.getByText("Goal g")).toBeTruthy();
    expect(screen.getByText("Flow w")).toBeTruthy();
    for (const gone of ["Loop old", "Goal old", "Flow stale"]) expect(screen.queryByText(gone)).toBeNull();
  });

  it("includes closed loops from the last week and drops older closed ones", () => {
    setup({ closedLoops: [loop("done", "closed", 1), loop("ancient", "closed", 30)] });
    expect(screen.getByText("loop · done")).toBeTruthy();
    expect(screen.queryByText("Loop ancient")).toBeNull();
  });

  it("orders newest first and says so when nothing changed", () => {
    const { container, rerender } = setup({ loops: [loop("a", "active", 4), loop("b", "active", 1)] });
    const titles = Array.from(container.querySelectorAll(".row .t")).map((n) => n.textContent);
    expect(titles).toEqual(["Loop b", "Loop a"]);
    rerender(<Touched loops={[]} closedLoops={[]} goals={[]} workflows={[]} loading={false} error={false} now={now} />);
    expect(screen.getByText("Nothing changed this week.")).toBeTruthy();
  });
});
