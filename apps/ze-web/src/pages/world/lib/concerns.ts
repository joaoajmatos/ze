import type { GoalListItem, HypothesisItem, LoopListItem, PriorityOverrideSchema, PrioritySnapshotItem, ReminderItem } from "@myguyze/ze-client";
import type { ConcernKind } from "@/shared/lib";

export interface Concern {
  /** `${kind}:${id}`, unique across kinds. */
  key: string;
  kind: ConcernKind;
  id: string;
  title: string;
  rank: number | null;
  computedRank: number | null;
  overridden: boolean;
  override: PriorityOverrideSchema | null;
  pinned: boolean;
  state: string | null;
  claimKind: string | null;
  provenance: string | null;
  confirmed: boolean;
  /** null means "not a claim": goals, relationships, reminders and records that failed to load. */
  confidence: number | null;
  /** Where confidence stood before it last changed; the trail is drawn only when present. */
  confidencePrior: number | null;
  due: Date | null;
  dueLabel: "drift deadline" | "reminder" | null;
  slipped: boolean;
  /** The snapshot named the item but its record did not load: title only. */
  partial: boolean;
  driftRationale: string | null;
  sources: string[];
  updatedAt: Date | null;
  reminderId: string | null;
  progress: { done: number; total: number; next: string | null; stuckSince: string | null } | null;
}

interface BuildInput {
  snapshot: PrioritySnapshotItem[];
  loops: LoopListItem[];
  goals: GoalListItem[];
  hypotheses: HypothesisItem[];
  reminders: ReminderItem[];
  now: Date;
}

const date = (s: string | null | undefined) => (s ? new Date(s) : null);

function base(kind: ConcernKind, id: string, title: string): Concern {
  return {
    key: `${kind}:${id}`,
    kind,
    id,
    title,
    rank: null,
    computedRank: null,
    overridden: false,
    override: null,
    pinned: false,
    state: null,
    claimKind: null,
    provenance: null,
    confirmed: false,
    confidence: null,
    confidencePrior: null,
    due: null,
    dueLabel: null,
    slipped: false,
    partial: false,
    driftRationale: null,
    sources: [],
    updatedAt: null,
    reminderId: null,
    progress: null,
  };
}

function isOpenReminder(r: ReminderItem): boolean {
  return r.status === "upcoming" || r.status === "overdue";
}

/** The field's set: what PriorityView ranks, joined to its records, plus reminders as deadlines. */
export function buildConcerns({ snapshot, loops, goals, hypotheses, reminders }: BuildInput): Concern[] {
  const loopById = new Map(loops.map((l) => [l.id, l]));
  const goalById = new Map(goals.map((g) => [g.id, g]));
  const hypById = new Map(hypotheses.map((h) => [h.id, h]));
  const reminderById = new Map(reminders.map((r) => [r.id, r]));
  const linkedReminders = new Set<string>();
  const out: Concern[] = [];

  for (const it of snapshot) {
    const c = base(it.source_kind, it.source_id, it.title);
    c.rank = it.displayed_rank;
    c.computedRank = it.computed_rank;
    c.overridden = it.overridden_from_computed;
    c.override = it.override;
    c.pinned = it.override?.pinned ?? false;

    if (it.source_kind === "loop") {
      const l = loopById.get(it.source_id);
      if (!l) c.partial = true;
      else {
        c.title = l.title;
        c.state = l.state;
        c.claimKind = l.claim_kind;
        c.provenance = l.provenance;
        c.confidence = l.confidence;
        c.confidencePrior = l.confidence_prior;
        c.slipped = l.state === "drifting";
        c.driftRationale = l.drift_rationale;
        c.sources = l.source_inflows;
        c.updatedAt = date(l.updated_at);
        c.reminderId = l.reminder_id;
        const drift = date(l.drift_deadline);
        const linked = l.reminder_id ? reminderById.get(l.reminder_id) : undefined;
        if (l.reminder_id) linkedReminders.add(l.reminder_id);
        const rem = linked && isOpenReminder(linked) ? date(linked.fire_at) : null;
        if (drift && rem) {
          c.due = rem < drift ? rem : drift;
          c.dueLabel = rem < drift ? "reminder" : "drift deadline";
        } else if (rem) {
          c.due = rem;
          c.dueLabel = "reminder";
        } else if (drift) {
          c.due = drift;
          c.dueLabel = "drift deadline";
        }
      }
    } else if (it.source_kind === "goal") {
      const g = goalById.get(it.source_id);
      c.slipped = true;
      if (!g) c.partial = true;
      else {
        c.title = g.title;
        c.state = g.status;
        c.updatedAt = date(g.last_progress_at);
        c.progress = { done: g.milestones_done, total: g.milestones_total, next: g.next_milestone, stuckSince: g.stuck_since };
      }
    } else if (it.source_kind === "hypothesis") {
      const h = hypById.get(it.source_id);
      if (!h) c.partial = true;
      else {
        c.title = h.summary;
        c.claimKind = h.claim_kind;
        c.confidence = h.confidence;
        c.confirmed = h.confirmed;
        c.state = h.confirmed ? "confirmed" : "open";
        c.updatedAt = date(h.created_at);
      }
    }
    out.push(c);
  }

  // Loops outside the snapshot still own their reminders, so those are not repeated below.
  for (const l of loops) if (l.reminder_id) linkedReminders.add(l.reminder_id);

  for (const r of reminders) {
    if (!isOpenReminder(r) || linkedReminders.has(r.id)) continue;
    const c = base("reminder", r.id, r.label);
    c.state = r.status;
    c.due = date(r.fire_at);
    c.dueLabel = "reminder";
    c.slipped = r.status === "overdue";
    out.push(c);
  }
  return out;
}
