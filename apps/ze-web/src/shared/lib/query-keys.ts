import type { UiManifestResponse } from "@myguyze/ze-client";

export const queryKeys = {
  goals: ["goals"] as const,
  goalDetail: (goalId: string) => ["goal-detail", goalId] as const,
  goalTraces: (goalId: string, milestoneId?: string) =>
    ["goal-traces", goalId, milestoneId ?? ""] as const,
  workflows: ["workflows"] as const,
  workflowDetail: (workflowId: string) => ["workflow-detail", workflowId] as const,
  workflowExecutions: (workflowId: string) => ["workflow-executions", workflowId] as const,
  workflowRevisions: (workflowId: string) => ["workflow-revisions", workflowId] as const,
  costs: ["costs"] as const,
  costAnomalies: ["cost-anomalies"] as const,
  sessions: ["sessions"] as const,
  sessionSearch: (query: string) => ["sessions", "search", query] as const,
  uiManifest: ["ui-manifest"] as const,
  memoryFeed: (type: string, agent?: string, asOf?: string) => ["memory-feed", type, agent ?? "", asOf ?? ""] as const,
  messageTrace: (messageId: string) => ["message-trace", messageId] as const,
  messageFeedbackAll: ["message-feedback"] as const,
  messageFeedback: (idsKey: string) => ["message-feedback", idsKey] as const,
  messageTraces: (threadId: string, idsKey: string) =>
    ["message-traces", threadId, idsKey] as const,
  memoryGraph: (entityType?: string, seedId?: string) => ["memory-graph", entityType ?? "", seedId ?? ""] as const,
  entityDetail: (entityId: string) => ["entity-detail", entityId] as const,
  pluginPage: (path: string) => ["plugin-page", path] as const,
  pluginSettings: (id: string) => ["plugin-settings", id] as const,
  dataDomains: () => ["data-domains"] as const,
  notifications: (unreadOnly: boolean) => ["notifications", unreadOnly] as const,
  notificationsDelivery: (delivery: string) => ["notifications-delivery", delivery] as const,
  unreadNotificationCount: ["unread-notification-count"] as const,
  quietHours: ["quiet-hours"] as const,
  notificationsSince: (since: string) => ["notifications-since", since] as const,
  attentionBudget: ["attention-budget"] as const,
  remindersAll: ["reminders"] as const,
  hypothesesAll: ["hypotheses"] as const,
  notificationsSinceAll: ["notifications-since"] as const,
  workflowExecutionsAll: ["workflow-executions"] as const,
  reminders: (status: string) => ["reminders", status] as const,
  hypotheses: (state: string, entityId?: string) => ["hypotheses", state, entityId ?? ""] as const,
  proactiveJobRuns: (since: string) => ["proactive-job-runs", since] as const,
  heldWrites: ["held-writes"] as const,
  loopsAll: ["loops"] as const,
  loops: (state?: string) => ["loops", state ?? ""] as const,
  loopDetail: (loopId: string) => ["loop-detail", loopId] as const,
  skills: (status?: string, source?: string) =>
    ["skills", status ?? "", source ?? ""] as const,
  skillDetail: (skillId: string) => ["skill-detail", skillId] as const,
  prioritySnapshot: () => ["priority-snapshot"] as const,
  workspace: () => ["workspace"] as const,
  workspaceFiles: (path?: string) => ["workspace-files", path ?? ""] as const,
  workspaceRuns: (origin?: string) => ["workspace-runs", origin ?? ""] as const,
  procedureCandidates: () => ["procedure-candidates"] as const,
  procedureLibrary: () => ["procedure-library"] as const,
  procedureDetail: (procedureId: string) => ["procedure-detail", procedureId] as const,
};

const CORE_REFRESH_SCREEN_MAP: Record<string, readonly (readonly string[])[]> = {
  goals: [queryKeys.goals, queryKeys.prioritySnapshot(), queryKeys.workflowExecutionsAll],
  workflows: [queryKeys.workflows],
  costs: [queryKeys.costs],
};

/** The query keys a `refresh` frame for `screen` invalidates. */
export function refreshKeysForScreen(
  screen: string,
  manifest?: UiManifestResponse | null,
): readonly (readonly string[])[] | undefined {
  const coreKeys = CORE_REFRESH_SCREEN_MAP[screen];
  if (coreKeys) {
    return coreKeys;
  }

  const pluginEntry = manifest?.nav.find((item) => item.path === screen);
  if (pluginEntry) {
    return [queryKeys.pluginPage(pluginEntry.id)];
  }

  return undefined;
}
