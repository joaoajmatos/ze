export function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export interface NotificationTarget {
  target_type: string | null;
  target_id: string | null;
  target_parent_id?: string | null;
}

/** Route for a notification's deep link target, or null if it has none / isn't navigable. */
export function notificationHref(n: NotificationTarget): string | null {
  const { target_type: type, target_id: id, target_parent_id: parent } = n;
  if (!type || !id) return null;
  if (type === "goal") return `/goals/${id}`;
  if (type === "goal_gate") return parent ? `/goals/${parent}` : null;
  if (type === "workflow_execution") {
    return parent ? `/workflows/${parent}?execution=${id}` : null;
  }
  return null;
}
