import type { AttentionBudgetResponse, NotificationItem, WsScreenRef } from "@myguyze/ze-client";
import { Link } from "react-router-dom";
import type { VisibleJobRun } from "@/entities/proactive-job";
import { useScreenPublisher } from "@/entities/screen-context";
import { agoPhrase, hhmm, notificationHref } from "@/shared/lib";
import { ChatAboutChip, Dots, Module } from "@/shared/ui";

interface Props {
  notifications: NotificationItem[];
  jobRuns: VisibleJobRun[];
  budget: AttentionBudgetResponse | null;
  loading: boolean;
  error: boolean;
  now: Date;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

const RUN_WORDS: Record<VisibleJobRun["last_status"], string> = { ok: "ran", error: "failed", running: "running" };

/** Notifications and job runs since the last visit, each with one action, and the interruption budget. */
export function Away({ notifications, jobRuns, budget, loading, error, now, onChatAbout }: Props) {
  const refOf = (n: NotificationItem): WsScreenRef =>
    n.target_type === "workflow_execution" && n.target_id
      ? ({ kind: "workflow_execution", id: n.target_id, parent_id: n.target_parent_id ?? undefined } as WsScreenRef)
      : ({ kind: "notification", id: n.id } as WsScreenRef);

  useScreenPublisher({ visible: notifications.slice(0, 10).map(refOf) });

  return (
    <Module label="While you were away" className="world-away">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read what happened while you were away.
        </p>
      ) : loading ? (
        <p className="muted">Reading…</p>
      ) : (
        <>
          {notifications.length === 0 && jobRuns.length === 0 && <p className="muted">Quiet.</p>}
          {notifications.slice(0, 6).map((n) => {
            const href = notificationHref(n);
            return (
              <div key={n.id} className="row">
                <span className="t">{n.title}</span>
                <span className="ro">{agoPhrase(new Date(n.delivered_at ?? n.created_at), now)}</span>
                <span className="acts">
                  {href && (
                    <Link to={href} className="ctl">
                      Open
                    </Link>
                  )}
                  {onChatAbout && <ChatAboutChip label={n.title} onClick={() => onChatAbout(refOf(n), null)} />}
                </span>
              </div>
            );
          })}
          {jobRuns.map((r) => (
            <div key={r.job_id} className={`row ${r.last_status === "error" ? "hot" : ""}`}>
              <span className="t">{r.label}</span>
              <span className={`lbl ${r.last_status === "error" ? "hot" : ""}`}>{RUN_WORDS[r.last_status]}</span>
              <span className="s">{agoPhrase(new Date(r.last_finished_at ?? r.last_started_at), now)}</span>
            </div>
          ))}
          {budget && (
            <div className="row">
              <span className="t">Push budget</span>
              <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                <Dots max={budget.max_per_day} lit={budget.used} label={`${budget.used} of ${budget.max_per_day} discretionary pushes used in the last ${budget.window_hours} hours`} />
                <span className="ro">
                  {budget.used} of {budget.max_per_day} used
                </span>
              </span>
              {budget.next_slot_at && <span className="s">Next slot {hhmm(new Date(budget.next_slot_at))}</span>}
            </div>
          )}
        </>
      )}
    </Module>
  );
}
