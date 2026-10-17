interface JobLabel {
  label: string;
  visible: boolean;
}

/** Closed map of every registered proactive job. Housekeeping jobs stay hidden from the user. */
export const JOB_LABELS: Record<string, JobLabel> = {
  morning_briefing: { label: "Morning briefing", visible: true },
  insight_generation: { label: "Weekly insights", visible: true },
  weekly_accountability: { label: "Weekly accountability", visible: true },
  goal_advance_sweep: { label: "Goal progress check", visible: true },
  goal_suggestion: { label: "Goal suggestions", visible: true },
  goal_narrative: { label: "Goal narrative", visible: true },
  stuck_goals: { label: "Stuck goal check", visible: true },
  worldstate_drift_sweep: { label: "Open loop drift check", visible: true },
  correlation_scan: { label: "Pattern scan", visible: true },
  attention_arbitration_sweep: { label: "Attention sweep", visible: true },
  calendar_reminder_sync: { label: "Calendar reminders", visible: true },
  inbound_poll: { label: "Inbox check", visible: true },
  news_fetch: { label: "News refresh", visible: true },
  dream_memory: { label: "Memory reflection", visible: true },
  cost_anomaly: { label: "Cost anomaly check", visible: true },
  contact_review: { label: "Contact review", visible: true },
  social_cooccurrence: { label: "Relationship scan", visible: true },
  quiet_hours_release: { label: "Quiet hours summary", visible: true },
  held_write_expiry: { label: "Held write expiry", visible: false },
  worldstate_stale_suspicion_sweep: { label: "Stale suspicion cleanup", visible: false },
  hypothesis_decay_sweep: { label: "Hypothesis decay", visible: false },
  dream_inactivity_watcher: { label: "Dream watcher", visible: false },
  memory_consolidation: { label: "Memory consolidation", visible: false },
  session_summary: { label: "Session summary", visible: false },
  prune_notifications: { label: "Notification cleanup", visible: false },
  skills_recheck: { label: "Skill recheck", visible: false },
  cost_reconciliation: { label: "Cost reconciliation", visible: false },
  checkpoint_pruning: { label: "Checkpoint pruning", visible: false },
  gmail_watch_renewal: { label: "Gmail watch renewal", visible: false },
  contacts_consolidation: { label: "Contacts consolidation", visible: false },
  recover_stale_campaigns: { label: "Campaign recovery", visible: false },
};

/** The label to show for a job, or null when the job is housekeeping or unknown. */
export function jobLabel(jobId: string): string | null {
  const entry = JOB_LABELS[jobId];
  return entry?.visible ? entry.label : null;
}
