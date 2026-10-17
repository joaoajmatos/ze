import type { AttentionBudgetResponse, GoalListItem, LoopListItem, NotificationItem, WorkflowExecutionResponse, WorkflowResponse } from "@myguyze/ze-client";
import { useEffect, useMemo, useState } from "react";
import { usePendingConfirms } from "@/features/respond-to-confirmation";
import { useHeldWritesQuery } from "@/entities/confirmation";
import { useGoalsQuery } from "@/entities/goal";
import { useHypothesesQuery } from "@/entities/hypothesis";
import { useLoopsQuery } from "@/entities/loop";
import { useAttentionBudgetQuery, useNotificationsSinceQuery } from "@/entities/notification";
import { usePrioritySnapshotQuery } from "@/entities/priority-item";
import { useProactiveJobRunsQuery, type VisibleJobRun } from "@/entities/proactive-job";
import { useRemindersQuery } from "@/entities/reminder";
import { useLatestExecutionsQuery, useWorkflowsQuery } from "@/entities/workflow";
import { buildConcerns, type Concern } from "../lib/concerns";
import { buildDecisions, type Decision } from "../lib/decisions";
import { useLastSeen } from "../lib/last-seen";
import { worldSentence, type SentenceCounts } from "../lib/sentence";

export interface Part<T> {
  data: T;
  loading: boolean;
  error: boolean;
}

export interface WorldModel {
  loading: boolean;
  now: Date;
  /** The start of this visit; "while you were away" counts from here. */
  since: Date;
  /** Priority sources that failed to read, named by the snapshot. */
  sourcesFailed: string[];
  field: Part<Concern[]>;
  /** Record sources the field joins that failed to load; their marks stay hollow with details unavailable. */
  recordsFailed: string[];
  decisions: Part<Decision[]>;
  loops: Part<LoopListItem[]>;
  doing: Part<{ goals: GoalListItem[]; workflows: WorkflowResponse[]; executions: Record<string, WorkflowExecutionResponse[]> }>;
  touched: Part<{ closedLoops: LoopListItem[]; loops: LoopListItem[]; goals: GoalListItem[]; workflows: WorkflowResponse[] }>;
  away: Part<{ notifications: NotificationItem[]; jobRuns: VisibleJobRun[]; budget: AttentionBudgetResponse | null }>;
  counts: SentenceCounts;
  sentence: string;
  /** A workflow whose latest run is still going. */
  running: boolean;
  /** A failed latest run counts as slipped for the orb. */
  failedRun: boolean;
}

const NONE: never[] = [];
const MINUTE = 60_000;

function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), MINUTE);
    return () => clearInterval(id);
  }, []);
  return now;
}

export function useWorld(): WorldModel {
  const now = useNow();
  const since = useLastSeen();
  const sinceIso = since.toISOString();

  const snapshot = usePrioritySnapshotQuery();
  const loopsQ = useLoopsQuery();
  const closedQ = useLoopsQuery("closed");
  const goalsQ = useGoalsQuery();
  const workflowsQ = useWorkflowsQuery();
  const heldQ = useHeldWritesQuery();
  const remindersQ = useRemindersQuery({ status: "all", limit: 100 });
  const hypothesesQ = useHypothesesQuery({ state: "all", limit: 200 });
  const notificationsQ = useNotificationsSinceQuery(sinceIso);
  const jobsQ = useProactiveJobRunsQuery(sinceIso);
  const budgetQ = useAttentionBudgetQuery();
  const pendingByThread = usePendingConfirms((s) => s.byThread);

  const workflows = workflowsQ.data ?? NONE;
  const latest = useLatestExecutionsQuery(useMemo(() => workflows.map((w) => w.id), [workflows]));

  const loops = loopsQ.data ?? NONE;
  const goals = goalsQ.data ?? NONE;

  const concerns = useMemo(
    () =>
      buildConcerns({
        snapshot: snapshot.data?.items ?? NONE,
        loops,
        goals,
        hypotheses: hypothesesQ.data ?? NONE,
        reminders: remindersQ.data ?? NONE,
        now,
      }),
    [snapshot.data, loops, goals, hypothesesQ.data, remindersQ.data, now],
  );

  const decisions = useMemo(
    () => buildDecisions({ held: heldQ.data ?? NONE, goals, loops, pendingByThread }),
    [heldQ.data, goals, loops, pendingByThread],
  );

  const counts: SentenceCounts = {
    slipped: concerns.filter((c) => c.slipped).length,
    watched: concerns.length,
    waiting: decisions.length,
  };

  const latestRuns = Object.values(latest.byWorkflow).map((runs) => runs[0]).filter(Boolean);
  const running = latestRuns.some((r) => r.status === "running");
  // A failure older than the week "Runs · 7 d" covers is history, not an alarm.
  const failedRun = latestRuns.some((r) => r.status === "failed" && now.getTime() - new Date(r.started_at ?? r.created_at).getTime() <= 7 * 86_400_000);

  // Until every record has loaded the join is incomplete, so the field waits rather than plot partial marks.
  const field: Part<Concern[]> = {
    data: concerns,
    loading: snapshot.isPending || loopsQ.isPending || goalsQ.isPending || hypothesesQ.isPending || remindersQ.isPending,
    error: snapshot.isError,
  };
  const recordsFailed = [
    loopsQ.isError && "loops",
    goalsQ.isError && "goals",
    hypothesesQ.isError && "hypotheses",
    remindersQ.isError && "reminders",
  ].filter((x): x is string => typeof x === "string");
  const decisionsPart: Part<Decision[]> = { data: decisions, loading: heldQ.isPending || goalsQ.isPending, error: heldQ.isError || goalsQ.isError };
  const loopsPart: Part<LoopListItem[]> = { data: loops, loading: loopsQ.isPending, error: loopsQ.isError };
  const doing: WorldModel["doing"] = {
    data: { goals, workflows, executions: latest.byWorkflow },
    loading: goalsQ.isPending || workflowsQ.isPending || latest.loading,
    error: goalsQ.isError || workflowsQ.isError || latest.error,
  };
  const touched: WorldModel["touched"] = {
    data: { closedLoops: closedQ.data ?? NONE, loops, goals, workflows },
    loading: closedQ.isPending || goalsQ.isPending || workflowsQ.isPending,
    error: closedQ.isError || goalsQ.isError || workflowsQ.isError,
  };
  const away: WorldModel["away"] = {
    data: { notifications: notificationsQ.data ?? NONE, jobRuns: jobsQ.data ?? NONE, budget: budgetQ.data ?? null },
    loading: notificationsQ.isPending || jobsQ.isPending || budgetQ.isPending,
    error: notificationsQ.isError || jobsQ.isError || budgetQ.isError,
  };

  return {
    loading: field.loading,
    now,
    since,
    sourcesFailed: snapshot.data?.sourcesFailed ?? NONE,
    field,
    recordsFailed,
    decisions: decisionsPart,
    loops: loopsPart,
    doing,
    touched,
    away,
    counts,
    sentence: worldSentence(counts),
    running,
    failedRun,
  };
}
