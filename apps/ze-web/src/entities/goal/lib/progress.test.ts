import type { GoalListItem } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { boardOrder, goalRow, progressLines, statusWord } from "./progress";

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

describe("goalRow", () => {
  it("derives the row from the list item alone", () => {
    const row = goalRow(
      goal({
        milestones_done: 2,
        milestones_total: 5,
        next_milestone: "Draft",
        gate_open_since: "2026-10-12T09:00:00Z",
        stuck_since: "2026-10-05T09:00:00Z",
        created_at: "2026-10-01T00:00:00Z",
      }),
    );
    expect(row.done).toBe(2);
    expect(row.total).toBe(5);
    expect(row.next).toBe("Draft");
    expect(row.gateSince).toMatch(/Oct/);
    expect(row.stuckSince).toMatch(/Oct/);
    expect(row.age).toMatch(/Oct/);
  });

  it("has a word for every status and no raw enum", () => {
    for (const s of ["planning", "active", "awaiting_gate", "paused", "completed", "abandoned"]) {
      expect(statusWord(s)).not.toMatch(/_/);
      expect(statusWord(s)[0]).toMatch(/[A-Z]/);
    }
    expect(statusWord("weird_new")).toBe("Weird new");
  });
});

describe("boardOrder", () => {
  const at = (id: string, o: Partial<GoalListItem>) => goal({ id, ...o });
  it("puts stuck, then gate open, then recent progress, then paused, then finished", () => {
    const groups = boardOrder([
      at("done", { status: "completed" }),
      at("paused", { status: "paused" }),
      at("old", { last_progress_at: "2026-10-01T00:00:00Z" }),
      at("new", { last_progress_at: "2026-10-09T00:00:00Z" }),
      at("gate", { status: "awaiting_gate", gate_id: "g", gate_open_since: "2026-10-08T00:00:00Z" }),
      at("stuck", { stuck_since: "2026-10-02T00:00:00Z" }),
      at("plan", { status: "planning" }),
      at("gone", { status: "abandoned" }),
    ]);
    expect(groups.live.map((g) => g.id)).toEqual(["stuck", "gate", "new", "old", "plan"]);
    expect(groups.paused.map((g) => g.id)).toEqual(["paused"]);
    expect(groups.finished.map((g) => g.id)).toEqual(["done", "gone"]);
  });
});
