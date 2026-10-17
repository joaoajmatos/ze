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
