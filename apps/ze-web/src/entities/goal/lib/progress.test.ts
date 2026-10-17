import type { GoalListItem } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { progressLines } from "./progress";

function goal(overrides: Partial<GoalListItem>): GoalListItem {
  return {
    id: "g-1",
    title: "Ship it",
    objective: "Ship it",
    status: "active",
    created_at: "2026-10-01T00:00:00Z",
    milestones_done: 0,
    milestones_total: 0,
    next_milestone: null,
    gate_id: null,
    gate_title: null,
    gate_open_since: null,
    last_progress_at: null,
    stuck_since: null,
    ...overrides,
  };
}

describe("progressLines", () => {
  it("shows done of total and the next milestone", () => {
    const lines = progressLines(
      goal({ milestones_done: 2, milestones_total: 5, next_milestone: "Draft the page" }),
    );
    expect(lines.map((l) => l.text)).toEqual(["2/5 milestones done", "Next: Draft the page"]);
  });

  it("says a goal waits on the user since the gate fired, with the gate's title", () => {
    const [line] = progressLines(
      goal({ gate_id: "gate-1", gate_title: "Approve pricing", gate_open_since: "2026-10-12T09:00:00Z" }),
    );
    expect(line.text).toMatch(/^Waiting on you since .+: Approve pricing$/);
    expect(line.alarm).toBeUndefined();
  });

  it("names a stuck goal's date as an alarm line", () => {
    const [line] = progressLines(goal({ stuck_since: "2026-10-05T09:00:00Z" }));
    expect(line.text).toMatch(/^Stuck since /);
    expect(line.alarm).toBe(true);
  });

  it("does not repeat a stuck gate as a second line", () => {
    const lines = progressLines(
      goal({ gate_open_since: "2026-10-05T09:00:00Z", stuck_since: "2026-10-05T09:00:00Z" }),
    );
    expect(lines).toHaveLength(1);
  });

  it("shows nothing for a goal with no milestones yet", () => {
    expect(progressLines(goal({}))).toEqual([]);
  });
});
