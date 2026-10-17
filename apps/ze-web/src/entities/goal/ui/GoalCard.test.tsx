import type { GoalListItem } from "@myguyze/ze-client";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api/useStartGoalMutation", () => ({
  useStartGoalMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { GoalCard } from "./GoalCard";

const goal: GoalListItem = {
  id: "g-1",
  title: "Launch LedgerLite",
  objective: "Launch LedgerLite",
  status: "active",
  created_at: "2026-10-01T00:00:00Z",
  milestones_done: 2,
  milestones_total: 5,
  next_milestone: "Draft the landing page",
  gate_id: null,
  gate_title: null,
  gate_open_since: null,
  last_progress_at: "2026-10-03T00:00:00Z",
  stuck_since: "2026-10-03T00:00:00Z",
};

describe("GoalCard progress", () => {
  it.each(["row", "grid"] as const)("shows progress and stuck state in the %s variant", (variant) => {
    render(
      <MemoryRouter>
        <GoalCard goal={goal} variant={variant} />
      </MemoryRouter>,
    );
    expect(screen.getByText("2/5 milestones done")).toBeInTheDocument();
    expect(screen.getByText("Next: Draft the landing page")).toBeInTheDocument();
    expect(screen.getByText(/^Stuck since /)).toBeInTheDocument();
  });
});
