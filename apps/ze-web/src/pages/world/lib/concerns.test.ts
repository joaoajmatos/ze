import type { GoalListItem, HypothesisItem, LoopListItem, PrioritySnapshotItem, ReminderItem } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { buildConcerns } from "./concerns";

const now = new Date("2026-10-17T12:00:00Z");

const item = (source_kind: PrioritySnapshotItem["source_kind"], source_id: string, rank: number, extra: Partial<PrioritySnapshotItem> = {}): PrioritySnapshotItem => ({
  source_kind,
  source_id,
  title: `${source_kind} ${source_id}`,
  displayed_rank: rank,
  computed_rank: rank,
  overridden_from_computed: false,
  override: null,
  ...extra,
});

const loop = (id: string, extra: Partial<LoopListItem> = {}): LoopListItem => ({
  id,
  title: `loop ${id}`,
  state: "active",
  claim_kind: "fact",
  provenance: "email",
  confidence: 0.7,
  drift_rationale: null,
  goal_id: null,
  reminder_id: null,
  confidence_prior: null,
  confidence_changed_at: null,
  drift_deadline: null,
  confirmed_at: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-16T00:00:00Z",
  promoted: false,
  source_inflows: ["email"],
  ...extra,
});

const goal = (id: string, extra: Partial<GoalListItem> = {}): GoalListItem => ({
  id,
  title: `goal ${id}`,
  objective: "",
  status: "active",
  created_at: "2026-09-01T00:00:00Z",
  milestones_done: 1,
  milestones_total: 4,
  next_milestone: "Draft",
  gate_id: null,
  gate_title: null,
  gate_open_since: null,
  last_progress_at: "2026-10-01T00:00:00Z",
  stuck_since: "2026-10-05T00:00:00Z",
  ...extra,
});

const hyp = (id: string, extra: Partial<HypothesisItem> = {}): HypothesisItem => ({
  id,
  summary: `hypothesis ${id}`,
  narrative: "",
  relation: "pattern",
  confidence: 0.46,
  claim_kind: "inference",
  evidence: [],
  entities: [],
  surfaced: true,
  feedback: null,
  confirmed: false,
  created_at: "2026-10-10T00:00:00Z",
  ...extra,
});

const reminder = (id: string, fire_at: string, status: ReminderItem["status"] = "upcoming"): ReminderItem => ({ id, label: `reminder ${id}`, fire_at, sent_at: null, status });

const empty = { loops: [], goals: [], hypotheses: [], reminders: [], now };

describe("buildConcerns", () => {
  it("joins a loop with its record", () => {
    const [c] = buildConcerns({ ...empty, snapshot: [item("loop", "l1", 1)], loops: [loop("l1", { confidence: 0.62, confidence_prior: 0.8 })] });
    expect(c).toMatchObject({ kind: "loop", id: "l1", confidence: 0.62, confidencePrior: 0.8, partial: false, slipped: false, rank: 1 });
  });

  it("marks a drifting loop slipped", () => {
    const [c] = buildConcerns({ ...empty, snapshot: [item("loop", "l1", 1)], loops: [loop("l1", { state: "drifting" })] });
    expect(c.slipped).toBe(true);
  });

  it("joins a stuck goal with its progress, slipped, with no confidence", () => {
    const [c] = buildConcerns({ ...empty, snapshot: [item("goal", "g1", 1)], goals: [goal("g1")] });
    expect(c).toMatchObject({ kind: "goal", slipped: true, confidence: null, confidencePrior: null });
    expect(c.progress).toEqual({ done: 1, total: 4, next: "Draft", stuckSince: "2026-10-05T00:00:00Z" });
  });

  it("joins a confirmed hypothesis from the all-state list", () => {
    const [c] = buildConcerns({ ...empty, snapshot: [item("hypothesis", "h1", 1)], hypotheses: [hyp("h1", { confirmed: true })] });
    expect(c).toMatchObject({ kind: "hypothesis", confidence: 0.46, confirmed: true, state: "confirmed", slipped: false });
  });

  it("gives a relationship a title and rank only", () => {
    const [c] = buildConcerns({ ...empty, snapshot: [item("relationship", "p1", 3)] });
    expect(c).toMatchObject({ kind: "relationship", rank: 3, title: "relationship p1", confidence: null, partial: false });
  });

  it("keeps a partial concern with the title when the record is missing", () => {
    const cs = buildConcerns({ ...empty, snapshot: [item("loop", "gone", 1), item("goal", "gone2", 2), item("hypothesis", "gone3", 3)] });
    for (const c of cs) expect(c).toMatchObject({ partial: true, confidence: null });
    expect(cs[0].title).toBe("loop gone");
  });

  it("never plots a missing confidence at 0.5", () => {
    const cs = buildConcerns({ ...empty, snapshot: [item("goal", "g1", 1), item("relationship", "p1", 2)], goals: [goal("g1")] });
    expect(cs.every((c) => c.confidence === null)).toBe(true);
  });

  it("takes the earliest of the drift deadline and the linked reminder", () => {
    const [c] = buildConcerns({
      ...empty,
      snapshot: [item("loop", "l1", 1)],
      loops: [loop("l1", { drift_deadline: "2026-10-20T00:00:00Z", reminder_id: "r1" })],
      reminders: [reminder("r1", "2026-10-18T09:00:00Z")],
    });
    expect(c.due).toEqual(new Date("2026-10-18T09:00:00Z"));
    expect(c.dueLabel).toBe("reminder");
    const [d] = buildConcerns({
      ...empty,
      snapshot: [item("loop", "l1", 1)],
      loops: [loop("l1", { drift_deadline: "2026-10-18T00:00:00Z", reminder_id: "r1" })],
      reminders: [reminder("r1", "2026-10-25T09:00:00Z")],
    });
    expect(d.due).toEqual(new Date("2026-10-18T00:00:00Z"));
    expect(d.dueLabel).toBe("drift deadline");
  });

  it("has no deadline when neither source gives one", () => {
    const [c] = buildConcerns({ ...empty, snapshot: [item("loop", "l1", 1)], loops: [loop("l1")] });
    expect(c.due).toBeNull();
    expect(c.dueLabel).toBeNull();
  });

  it("ignores a fired reminder as a deadline", () => {
    const cs = buildConcerns({
      ...empty,
      snapshot: [item("loop", "l1", 1)],
      loops: [loop("l1", { reminder_id: "r1" })],
      reminders: [reminder("r1", "2026-10-10T09:00:00Z", "fired")],
    });
    expect(cs).toHaveLength(1);
    expect(cs[0].due).toBeNull();
  });

  it("turns an unlinked reminder into its own concern and an overdue one is slipped", () => {
    const cs = buildConcerns({
      ...empty,
      snapshot: [],
      reminders: [reminder("r1", "2026-10-19T09:00:00Z"), reminder("r2", "2026-10-15T09:00:00Z", "overdue"), reminder("r3", "2026-10-01T09:00:00Z", "fired")],
    });
    expect(cs.map((c) => [c.id, c.kind, c.slipped, c.confidence])).toEqual([
      ["r1", "reminder", false, null],
      ["r2", "reminder", true, null],
    ]);
    expect(cs[0].due).toEqual(new Date("2026-10-19T09:00:00Z"));
  });

  it("does not repeat a reminder that a loop already carries", () => {
    const cs = buildConcerns({
      ...empty,
      snapshot: [item("loop", "l1", 1)],
      loops: [loop("l1", { reminder_id: "r1" })],
      reminders: [reminder("r1", "2026-10-19T09:00:00Z")],
    });
    expect(cs.map((c) => c.kind)).toEqual(["loop"]);
  });

  it("marks a loop slipped when its linked reminder is overdue", () => {
    const [c] = buildConcerns({
      ...empty,
      snapshot: [item("loop", "l1", 1)],
      loops: [loop("l1", { reminder_id: "r1" })],
      reminders: [reminder("r1", "2026-10-15T09:00:00Z", "overdue")],
    });
    expect(c.slipped).toBe(true);
    expect(c.due).toEqual(new Date("2026-10-15T09:00:00Z"));
  });

  it("keeps the reminder of a suspected loop as its own mark", () => {
    const cs = buildConcerns({
      ...empty,
      snapshot: [],
      loops: [loop("l1", { state: "suspected", reminder_id: "r1" })],
      reminders: [reminder("r1", "2026-10-19T09:00:00Z")],
    });
    expect(cs.map((c) => [c.kind, c.id])).toEqual([["reminder", "r1"]]);
  });

  it("draws a trail only when confidence_prior is present", () => {
    const [a, b] = buildConcerns({
      ...empty,
      snapshot: [item("loop", "l1", 1), item("loop", "l2", 2)],
      loops: [loop("l1", { confidence_prior: 0.9 }), loop("l2")],
    });
    expect(a.confidencePrior).toBe(0.9);
    expect(b.confidencePrior).toBeNull();
  });

  it("carries the override and pin from the snapshot", () => {
    const override = { id: "o1", pinned: true } as PrioritySnapshotItem["override"];
    const [c] = buildConcerns({ ...empty, snapshot: [item("loop", "l1", 2, { computed_rank: 5, overridden_from_computed: true, override })], loops: [loop("l1")] });
    expect(c).toMatchObject({ rank: 2, computedRank: 5, overridden: true, pinned: true });
  });
});
