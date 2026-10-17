// Prototype data layer: composes the real REST data into one world-state view.
// Fields the API does not expose yet are filled from the ze_e2e_web fixture and
// flagged `synthetic` so every direction can mark them on screen.
import { getGoalDetail, listWorkflowExecutions } from "@myguyze/ze-client";
import type {
  GoalDetailResponse,
  HeldWriteOut,
  LoopListItem,
  MemoryFeedItem,
  NotificationItem,
  PrioritySnapshotItem,
  WorkflowExecutionResponse,
  WorkflowResponse,
} from "@myguyze/ze-client";
import { useQueries } from "@tanstack/react-query";
import { useHeldWritesQuery } from "@/entities/confirmation";
import { useGoalsQuery } from "@/entities/goal";
import { useLoopsQuery } from "@/entities/loop";
import { useMemoryFeedQuery } from "@/entities/memory-feed-item";
import { useMemoryGraphQuery } from "@/entities/memory-graph";
import { useNotificationsQuery } from "@/entities/notification";
import { usePrioritySnapshotQuery } from "@/entities/priority-item";
import { useQuietHoursQuery } from "@/entities/quiet-hours";
import { useWorkflowsQuery } from "@/entities/workflow";
import { goalPath } from "@/shared/config";

// API gap 1: LoopListItem has no drift_deadline. Values copied from open_loops in ze_e2e_web.
const DRIFT_DEADLINES: Record<string, string> = {
  "a0000000-0000-4000-8000-000000000006": "2026-10-11T23:05:09Z",
  "a0000000-0000-4000-8000-000000000003": "2026-10-14T23:05:09Z",
  "a0000000-0000-4000-8000-000000000001": "2026-10-17T23:05:09Z",
  "a0000000-0000-4000-8000-000000000007": "2026-10-18T23:05:09Z",
  "a0000000-0000-4000-8000-000000000002": "2026-10-19T23:05:09Z",
};

// API gap 7: reminders exist only as server-driven UI. Rows copied from user_reminders.
const REMINDERS = [
  { id: "0000000a-0001-4000-8000-000000000002", title: "Prep standup notes for Marco", at: "2026-10-17T23:02:48Z" },
  { id: "0000000a-0001-4000-8000-000000000001", title: "Dentist appointment — bring insurance card", at: "2026-10-21T23:02:48Z" },
];

// API gap 2: priority items carry no reason. Hypothesis confidences from correlation_hypothesis.
const HYPOTHESIS_CONFIDENCE: Record<string, number> = {
  "b0000000-0000-4000-8000-000000000001": 0.46,
  "b0000000-0000-4000-8000-000000000002": 0.58,
};

export type ConcernKind = "loop" | "goal" | "hypothesis" | "relationship";

export interface Concern {
  id: string;
  kind: ConcernKind;
  title: string;
  rank: number | null;
  pinned: boolean;
  state: string;
  claimKind: string;
  confidence: number | null;
  provenance: string | null;
  sources: string[];
  driftRationale: string | null;
  due: Date | null;
  dueSynthetic: boolean;
  updatedAt: Date | null;
  createdAt: Date | null;
  promoted: boolean;
  hasReminder: boolean;
  goalId: string | null;
}

export type DecisionKind = "held_write" | "gate" | "suspicion" | "fact_review" | "learning";

export interface Decision {
  id: string;
  kind: DecisionKind;
  title: string;
  detail: string;
  origin: string;
  at: Date | null;
  expiresAt: Date | null;
  confidence: number | null;
  proposedText: string | null;
  href: string | null;
}

export interface HorizonItem {
  id: string;
  title: string;
  kind: "drift" | "reminder" | "workflow" | "gate";
  at: Date;
  overdue: boolean;
  synthetic: boolean;
}

export interface AwayEvent {
  id: string;
  at: Date;
  title: string;
  body: string;
  outcome: "ok" | "failed" | "held" | "info";
  origin: string;
}

export interface GoalView {
  id: string;
  title: string;
  objective: string;
  status: string;
  done: number;
  total: number;
  openGate: { title: string; firedAt: Date | null; summary: string | null } | null;
  milestones: { title: string; status: string; completedAt: Date | null }[];
}

export interface WorkflowView {
  id: string;
  name: string;
  schedule: string | null;
  enabled: boolean;
  nextRun: Date | null;
  lastRun: Date | null;
  runs: { id: string; ok: boolean; at: Date; durationMs: number | null }[];
}

export interface World {
  loading: boolean;
  now: Date;
  concerns: Concern[];
  closed: Concern[];
  decisions: Decision[];
  horizon: HorizonItem[];
  away: AwayEvent[];
  goals: GoalView[];
  workflows: WorkflowView[];
  noticed: MemoryFeedItem[];
  facts: MemoryFeedItem[];
  people: { id: string; name: string; type: string; role: string | null; degree: number }[];
  budget: { max: number; spent: number; spentSynthetic: boolean; quietEnabled: boolean; quietNow: boolean; held: number };
  sourcesFailed: string[];
}

const d = (s: string | null | undefined) => (s ? new Date(s) : null);

function loopConcern(loop: LoopListItem, item?: PrioritySnapshotItem): Concern {
  const due = DRIFT_DEADLINES[loop.id];
  return {
    id: loop.id,
    kind: "loop",
    title: loop.title,
    rank: item?.displayed_rank ?? null,
    pinned: item?.override?.pinned ?? false,
    state: loop.state,
    claimKind: loop.claim_kind,
    confidence: loop.confidence,
    provenance: loop.provenance,
    sources: loop.source_inflows,
    driftRationale: loop.drift_rationale,
    due: due ? new Date(due) : null,
    dueSynthetic: Boolean(due),
    updatedAt: d(loop.updated_at),
    createdAt: d(loop.created_at),
    promoted: loop.promoted,
    hasReminder: Boolean(loop.reminder_id),
    goalId: loop.goal_id,
  };
}

export function useWorld(): World {
  const now = new Date();
  const open = useLoopsQuery();
  const closedQ = useLoopsQuery("closed");
  const droppedQ = useLoopsQuery("dropped");
  const snapshot = usePrioritySnapshotQuery();
  const goalsQ = useGoalsQuery();
  const held = useHeldWritesQuery();
  const notes = useNotificationsQuery();
  const feed = useMemoryFeedQuery({ type: "fact" });
  const quiet = useQuietHoursQuery();
  const wfQ = useWorkflowsQuery();
  const graph = useMemoryGraphQuery({ limit: 40 });

  const goalList = goalsQ.data ?? [];
  const goalDetails = useQueries({
    queries: goalList.map((g) => ({
      queryKey: ["jarvis", "goal", g.id],
      queryFn: async () => (await getGoalDetail({ path: { goal_id: g.id } })).data as GoalDetailResponse,
    })),
  });
  const wfList: WorkflowResponse[] = (wfQ.data as WorkflowResponse[] | undefined) ?? [];
  const wfRuns = useQueries({
    queries: wfList.map((w) => ({
      queryKey: ["jarvis", "wf-runs", w.id],
      queryFn: async () =>
        ((await listWorkflowExecutions({ path: { workflow_id: w.id } })).data ?? []) as WorkflowExecutionResponse[],
    })),
  });

  const loops = open.data ?? [];
  const snap = snapshot.data;
  const items: PrioritySnapshotItem[] = snap?.items ?? [];
  const byId = new Map(items.map((i) => [i.source_id, i]));

  const concerns: Concern[] = loops
    .filter((l) => l.state !== "closed" && l.state !== "dropped")
    .map((l) => loopConcern(l, byId.get(l.id)));

  for (const it of items) {
    if (it.source_kind === "loop") continue;
    const goal = goalList.find((g) => g.id === it.source_id);
    concerns.push({
      id: it.source_id,
      kind: it.source_kind,
      title: it.title,
      rank: it.displayed_rank,
      pinned: it.override?.pinned ?? false,
      state: it.source_kind === "goal" ? (goal?.status ?? "active") : it.source_kind === "hypothesis" ? "hypothesis" : "relationship",
      claimKind: it.source_kind === "hypothesis" ? "inference" : "priority",
      confidence: HYPOTHESIS_CONFIDENCE[it.source_id] ?? null,
      provenance: it.source_kind === "hypothesis" ? "correlation" : null,
      sources: [],
      driftRationale: null,
      due: null,
      dueSynthetic: false,
      updatedAt: null,
      createdAt: d(goal?.created_at),
      promoted: false,
      hasReminder: false,
      goalId: it.source_kind === "goal" ? it.source_id : null,
    });
  }
  concerns.sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));

  const closed = [...(closedQ.data ?? []), ...(droppedQ.data ?? [])].map((l) => loopConcern(l));

  const goals: GoalView[] = goalList.map((g, i) => {
    const det = goalDetails[i]?.data;
    const ms = det?.milestones ?? [];
    const firedGate = det?.gates.find((x) => x.status === "awaiting_approval");
    return {
      id: g.id,
      title: g.title,
      objective: g.objective,
      status: g.status,
      done: ms.filter((m) => m.status === "completed").length,
      total: ms.length,
      openGate: firedGate ? { title: firedGate.title, firedAt: d(firedGate.fired_at), summary: firedGate.context_summary } : null,
      milestones: ms.map((m) => ({ title: m.title, status: m.status, completedAt: d(m.completed_at) })),
    };
  });

  const decisions: Decision[] = [];
  for (const h of (held.data ?? []) as HeldWriteOut[]) {
    if (h.status !== "open") continue;
    for (const it of h.items) {
      decisions.push({
        id: `${h.request_id}:${it.item_id}`,
        kind: "held_write",
        title: it.effect_phrase.charAt(0).toUpperCase() + it.effect_phrase.slice(1),
        detail: it.summary,
        origin: h.source_name || (wfList.find((w) => w.id === h.owner_ref)?.name ?? h.source),
        at: d(h.created_at),
        expiresAt: d(h.expires_at),
        confidence: null,
        proposedText: it.proposed_text ?? null,
        href: null,
      });
    }
  }
  for (const g of goals) {
    if (g.openGate) {
      decisions.push({
        id: `gate:${g.id}`,
        kind: "gate",
        title: g.openGate.title,
        detail: g.openGate.summary ?? "",
        origin: g.title,
        at: g.openGate.firedAt,
        expiresAt: null,
        confidence: null,
        proposedText: null,
        href: goalPath(g.id),
      });
    }
  }
  for (const c of concerns.filter((x) => x.state === "suspected")) {
    decisions.push({
      id: `loop:${c.id}`,
      kind: "suspicion",
      title: c.title,
      detail: `Seen in ${c.sources.join(", ") || c.provenance}`,
      origin: c.provenance ?? "",
      at: c.createdAt,
      expiresAt: null,
      confidence: c.confidence,
      proposedText: null,
      href: null,
    });
  }
  const facts: MemoryFeedItem[] = feed.data?.pages[0]?.items ?? [];
  const noticed = facts.filter((f) => f.type === "fact" && f.reviewed === false).slice(0, 6);
  for (const f of noticed.slice(0, 2)) {
    decisions.push({
      id: `fact:${f.id}`,
      kind: "fact_review",
      title: f.value ?? f.key ?? "",
      detail: (f.key ?? "").replace(/_/g, " "),
      origin: f.agent,
      at: d(f.created_at),
      expiresAt: null,
      confidence: f.confidence,
      proposedText: null,
      href: "/mind",
    });
  }

  const workflows: WorkflowView[] = wfList.map((w, i) => ({
    id: w.id,
    name: w.name,
    schedule: w.schedule,
    enabled: w.enabled,
    nextRun: d(w.next_run_at),
    lastRun: d(w.last_run_at),
    runs: (wfRuns[i]?.data ?? [])
      .map((r) => {
        const start = d(r.started_at) ?? new Date(r.created_at);
        const end = d(r.completed_at);
        return { id: r.id, ok: r.status === "completed", at: start, durationMs: end ? end.getTime() - start.getTime() : null };
      })
      .sort((a, b) => a.at.getTime() - b.at.getTime())
      .slice(-14),
  }));

  const horizonEnd = new Date(now.getTime() + 7 * 86400_000);
  const horizon: HorizonItem[] = [];
  for (const c of concerns) {
    if (c.due && c.due <= horizonEnd) {
      horizon.push({ id: c.id, title: c.title, kind: "drift", at: c.due, overdue: c.due < now, synthetic: c.dueSynthetic });
    }
  }
  for (const r of REMINDERS) {
    const at = new Date(r.at);
    if (at <= horizonEnd) horizon.push({ id: r.id, title: r.title, kind: "reminder", at, overdue: at < now, synthetic: true });
  }
  for (const w of workflows) {
    if (w.enabled && w.nextRun && w.nextRun <= horizonEnd && w.nextRun >= now) {
      horizon.push({ id: w.id, title: w.name, kind: "workflow", at: w.nextRun, overdue: false, synthetic: false });
    }
  }
  for (const g of goals) {
    if (g.openGate?.firedAt) {
      horizon.push({ id: `gate:${g.id}`, title: g.openGate.title, kind: "gate", at: g.openGate.firedAt, overdue: true, synthetic: false });
    }
  }
  horizon.sort((a, b) => a.at.getTime() - b.at.getTime());

  const notifications: NotificationItem[] = notes.data?.pages[0]?.items ?? [];
  const away: AwayEvent[] = notifications.map((n) => ({
    id: n.id,
    at: new Date(n.created_at),
    title: n.title,
    body: n.body,
    outcome:
      n.event_type.includes("failure") ? "failed" : n.event_type.includes("held") ? "held" : n.event_type === "workflow_run" ? "ok" : "info",
    origin: n.source,
  }));

  // API gap 5: pushes spent today. Derived from today's delivered notifications that rang the bell.
  const today = now.toDateString();
  const spent = notifications.filter(
    (n) => new Date(n.created_at).toDateString() === today && n.delivery === "delivered" && n.push_class === "discretionary",
  ).length;

  return {
    loading: open.isLoading || snapshot.isLoading || goalsQ.isLoading,
    now,
    concerns,
    closed,
    decisions,
    horizon,
    away,
    goals,
    workflows,
    noticed,
    facts,
    people: (graph.data?.nodes ?? [])
      .filter((n) => n.attrs?.role !== "user" && (n.entity_type === "person" || n.entity_type === "topic" || n.entity_type === "org"))
      .slice(0, 10)
      .map((n) => ({
        id: n.id,
        name: n.canonical_name,
        type: n.entity_type,
        role: (n.attrs?.role as string | undefined) ?? (n.attrs?.kind as string | undefined) ?? null,
        degree: n.degree,
      })),
    budget: {
      max: quiet.data?.max_discretionary_per_day ?? 5,
      spent,
      spentSynthetic: false,
      quietEnabled: quiet.data?.enabled ?? false,
      quietNow: quiet.data?.active_now ?? false,
      held: quiet.data?.held_count ?? 0,
    },
    sourcesFailed: snap?.sourcesFailed ?? [],
  };
}
