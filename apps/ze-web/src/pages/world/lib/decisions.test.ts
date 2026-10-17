import type { GoalListItem, HeldWriteOut, LoopListItem } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import type { PendingConfirm } from "@/features/respond-to-confirmation";
import { buildDecisions } from "./decisions";

const held = (id: string, expires_at: string | null, created_at: string | null = "2026-10-17T08:00:00Z"): HeldWriteOut =>
  ({ request_id: id, source: "workflow", source_name: `Workflow ${id}`, owner_ref: "wf", items: [], status: "open", created_at, expires_at }) as HeldWriteOut;

const goal = (id: string, gate_id: string | null, since = "2026-10-17T07:00:00Z"): GoalListItem =>
  ({ id, title: `Goal ${id}`, status: gate_id ? "awaiting_gate" : "active", gate_id, gate_title: gate_id ? `Gate ${gate_id}` : null, gate_open_since: gate_id ? since : null }) as GoalListItem;

const loop = (id: string, state: string): LoopListItem => ({ id, title: `Loop ${id}`, state, created_at: "2026-10-17T06:00:00Z" }) as LoopListItem;

const pending = (id: string, threadId: string, kind: PendingConfirm["kind"], extra: Partial<PendingConfirm> = {}): PendingConfirm => ({
  id,
  threadId,
  kind,
  round: 1,
  title: `Confirm ${id}`,
  items: [],
  source: null,
  expiresAt: null,
  actions: [],
  submitted: false,
  ...extra,
});

const none = { held: [], goals: [], loops: [], pendingByThread: {} };

describe("buildDecisions", () => {
  it("lists held writes, gates, suspected loops and chat confirmations", () => {
    const ds = buildDecisions({
      held: [held("h1", null)],
      goals: [goal("g1", "gate1"), goal("g2", null)],
      loops: [loop("l1", "suspected"), loop("l2", "active")],
      pendingByThread: { t1: [pending("c1", "t1", "write")] },
    });
    expect(ds.map((d) => d.kind).sort()).toEqual(["chat_confirmation", "gate", "held_write", "suspected_loop"]);
    const gate = ds.find((d) => d.kind === "gate");
    expect(gate).toMatchObject({ id: "gate1", goalId: "g1", title: "Gate gate1" });
  });

  it("takes budget and write confirmations from every thread, not held or prompt ones", () => {
    const ds = buildDecisions({
      ...none,
      pendingByThread: {
        t1: [pending("a", "t1", "budget"), pending("b", "t1", "prompt")],
        t2: [pending("c", "t2", "write"), pending("d", "t2", "held")],
        "*": [pending("e", "*", "write")],
      },
    });
    expect(ds.map((d) => d.id).sort()).toEqual(["a", "c"]);
  });

  it("skips a confirmation already sent", () => {
    const ds = buildDecisions({ ...none, pendingByThread: { t1: [pending("a", "t1", "write", { submitted: true })] } });
    expect(ds).toEqual([]);
  });

  it("orders by expiry, soonest first, then by age", () => {
    const ds = buildDecisions({
      held: [held("late", "2026-10-18T12:00:00Z"), held("none-old", null, "2026-10-16T00:00:00Z"), held("soon", "2026-10-17T20:00:00Z"), held("none-new", null, "2026-10-17T09:00:00Z")],
      goals: [],
      loops: [],
      pendingByThread: {},
    });
    expect(ds.map((d) => d.id)).toEqual(["soon", "late", "none-old", "none-new"]);
  });

  it("yields no chat-confirmation rows from an empty pending store", () => {
    expect(buildDecisions({ ...none, held: [held("h1", null)] }).map((d) => d.kind)).toEqual(["held_write"]);
  });
});
