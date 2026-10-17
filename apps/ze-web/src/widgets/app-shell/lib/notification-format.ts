import { askPath, goalPath, goalsPath, workflowPath, workflowsPath } from "@/shared/config";

export function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

interface NotificationTarget {
  target_type: string | null;
  target_id: string | null;
  target_parent_id?: string | null;
}

/**
 * Where a notification opens (the 184 notification-targets table). Until the place phases
 * land, loops, hypotheses and reminders open World, people and insights open Mind.
 */
export function notificationHref(n: NotificationTarget): string | null {
  const { target_type: type, target_id: id, target_parent_id: parent } = n;
  if (!type || !id) return null;
  switch (type) {
    case "open_loop":
    case "hypothesis":
    case "held_write":
    case "reminder":
      return "/";
    case "goal":
      return goalPath(id);
    case "goal_gate":
      return parent ? goalPath(parent) : goalsPath();
    case "goal_suggestion":
      return "/doing";
    case "workflow_execution":
      return parent ? workflowPath(parent, id) : workflowsPath();
    case "workspace_run":
      return "/doing/workspace";
    case "chat_thread":
      return askPath(id);
    case "person":
    case "insight":
      return "/mind";
    default:
      return null;
  }
}
