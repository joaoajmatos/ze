import type { GoalListItem } from "@myguyze/ze-client";

export interface ProgressLine {
  text: string;
  alarm?: boolean;
}

function day(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Plain lines for a goal row: only what the API exposes, nothing derived. */
export function progressLines(goal: GoalListItem): ProgressLine[] {
  const lines: ProgressLine[] = [];
  if (goal.milestones_total > 0) {
    lines.push({ text: `${goal.milestones_done}/${goal.milestones_total} milestones done` });
  }
  if (goal.next_milestone) lines.push({ text: `Next: ${goal.next_milestone}` });
  if (goal.gate_open_since) {
    const gate = goal.gate_title ? `: ${goal.gate_title}` : "";
    lines.push({ text: `Waiting on you since ${day(goal.gate_open_since)}${gate}` });
  } else if (goal.stuck_since) {
    lines.push({ text: `Stuck since ${day(goal.stuck_since)}`, alarm: true });
  }
  return lines;
}

const STATUS_WORDS: Record<string, string> = {
  planning: "Plan ready",
  active: "In progress",
  awaiting_gate: "Waiting on you",
  paused: "Paused",
  completed: "Done",
  abandoned: "Abandoned",
};

export function statusWord(status: string): string {
  const known = STATUS_WORDS[status];
  if (known) return known;
  const spaced = status.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export interface GoalRow {
  done: number;
  total: number;
  next: string | null;
  gateSince: string | null;
  stuckSince: string | null;
  age: string;
}

export function goalRow(goal: GoalListItem): GoalRow {
  return {
    done: goal.milestones_done,
    total: goal.milestones_total,
    next: goal.next_milestone,
    gateSince: goal.gate_open_since ? day(goal.gate_open_since) : null,
    stuckSince: goal.stuck_since ? day(goal.stuck_since) : null,
    age: day(goal.created_at),
  };
}

export interface BoardGroups {
  live: GoalListItem[];
  paused: GoalListItem[];
  finished: GoalListItem[];
}

function rank(g: GoalListItem): number {
  if (g.stuck_since) return 0;
  if (g.gate_open_since || g.status === "awaiting_gate") return 1;
  return 2;
}

/** Live goals first (stuck, gate open, then last progress), then paused, then finished. */
export function boardOrder(goals: readonly GoalListItem[]): BoardGroups {
  const live = goals.filter((g) => g.status !== "paused" && g.status !== "completed" && g.status !== "abandoned");
  live.sort((a, b) => rank(a) - rank(b) || (b.last_progress_at ?? "").localeCompare(a.last_progress_at ?? ""));
  return {
    live,
    paused: goals.filter((g) => g.status === "paused"),
    finished: goals.filter((g) => g.status === "completed" || g.status === "abandoned"),
  };
}
