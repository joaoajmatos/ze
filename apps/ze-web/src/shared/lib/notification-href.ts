import { askPath, goalPath, goalsPath, workflowPath, workflowsPath } from "@/shared/config";

export type FocusKind = "loop" | "held_write" | "reminder" | "hypothesis" | "goal";

/** A World link that selects one item (`/?focus=<kind>:<id>`); chat cards and notifications share it. */
export function focusHref(kind: FocusKind, id: string): string {
  return `/?focus=${kind}:${encodeURIComponent(id)}`;
}

interface NotificationTarget {
  target_type: string | null;
  target_id: string | null;
  target_parent_id?: string | null;
}

/**
 * Where a notification opens (the 184 notification-targets table). Loops, hypotheses, reminders
 * and held writes open World with the item selected; people and insights open Mind.
 */
export function notificationHref(n: NotificationTarget): string | null {
  const { target_type: type, target_id: id, target_parent_id: parent } = n;
  if (!type || !id) return null;
  switch (type) {
    case "open_loop":
      return focusHref("loop", id);
    case "hypothesis":
    case "held_write":
    case "reminder":
      return focusHref(type, id);
    case "goal":
      return goalPath(id);
    case "goal_gate":
      return parent ? goalPath(parent) : goalsPath();
    case "goal_suggestion":
      return "/doing";
    case "workflow_execution":
      return parent ? workflowPath(parent, id) : workflowsPath();
    case "workspace_run":
      return "/governance#files";
    case "chat_thread":
      return askPath(id);
    case "person":
    case "insight":
      return "/mind";
    default:
      return null;
  }
}
