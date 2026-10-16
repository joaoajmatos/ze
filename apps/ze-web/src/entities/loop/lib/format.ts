import type { LoopListItem } from "@myguyze/ze-client";

const INFLOW_LABELS: Record<string, string> = {
  conversation: "chat",
  email: "email",
  calendar: "calendar",
  ingestion: "a document",
};

export function sourceLabel(inflow: string): string {
  return INFLOW_LABELS[inflow] ?? inflow;
}

export function promotedLine(
  item: Pick<LoopListItem, "promoted" | "source_inflows">
): string | null {
  if (!item.promoted) return null;
  const labels = item.source_inflows.map(sourceLabel);
  return labels.length > 0 ? `Promoted · seen in: ${labels.join(", ")}` : "Promoted";
}

export function linkChips(
  item: Pick<LoopListItem, "reminder_id" | "goal_id">
): string[] {
  const chips: string[] = [];
  if (item.reminder_id) chips.push("Has reminder");
  if (item.goal_id) chips.push("Linked goal");
  return chips;
}
