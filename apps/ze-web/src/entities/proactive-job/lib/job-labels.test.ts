import { describe, expect, it } from "vitest";
import { JOB_LABELS, jobLabel } from "./job-labels";

const REGISTERED = [
  "worldstate_stale_suspicion_sweep", "worldstate_drift_sweep", "correlation_scan", "hypothesis_decay_sweep",
  "dream_inactivity_watcher", "memory_consolidation", "session_summary", "dream_memory", "quiet_hours_release",
  "prune_notifications", "attention_arbitration_sweep", "skills_recheck", "goal_advance_sweep", "cost_anomaly",
  "goal_suggestion", "stuck_goals", "weekly_accountability", "held_write_expiry", "goal_narrative",
  "cost_reconciliation", "checkpoint_pruning", "news_fetch", "inbound_poll", "gmail_watch_renewal",
  "contacts_consolidation", "contact_review", "social_cooccurrence", "morning_briefing", "insight_generation",
  "calendar_reminder_sync", "recover_stale_campaigns",
];

describe("job labels", () => {
  it("has an entry for every registered job id", () => {
    for (const id of REGISTERED) expect(JOB_LABELS[id], id).toBeDefined();
  });

  it("hides housekeeping jobs", () => {
    for (const id of ["checkpoint_pruning", "prune_notifications", "cost_reconciliation", "memory_consolidation"]) {
      expect(jobLabel(id)).toBeNull();
    }
  });

  it("shows user-meaningful jobs with a label, and hides unknown ids", () => {
    expect(jobLabel("morning_briefing")).toBe("Morning briefing");
    expect(jobLabel("nope")).toBeNull();
  });
});
