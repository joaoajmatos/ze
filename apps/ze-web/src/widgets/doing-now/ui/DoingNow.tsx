import type { GoalListItem, WorkflowExecutionResponse, WorkflowResponse, WsScreenRef } from "@myguyze/ze-client";
import { useScreenPublisher } from "@/entities/screen-context";
import { hhmm, relDay } from "@/shared/lib";
import { Module } from "@/shared/ui";

interface Props {
  goals: GoalListItem[];
  workflows: WorkflowResponse[];
  /** Latest runs per workflow id, newest first. */
  executions: Record<string, WorkflowExecutionResponse[]>;
  loading: boolean;
  error: boolean;
  now: Date;
}

const WEEK = 7 * 86_400_000;
const LIVE_GOAL = new Set(["planning", "active", "awaiting_gate", "paused"]);

/** What Ze is working on: goals with progress, the next scheduled run, this week's runs, and a run in progress. */
export function DoingNow({ goals, workflows, executions, loading, error, now }: Props) {
  const active = goals.filter((g) => LIVE_GOAL.has(g.status));
  const next = workflows
    .filter((w) => w.enabled && w.next_run_at && new Date(w.next_run_at) >= now)
    .sort((a, b) => new Date(a.next_run_at!).getTime() - new Date(b.next_run_at!).getTime())[0];
  const nameOf = (id: string) => workflows.find((w) => w.id === id)?.name ?? "A workflow";
  const runs = Object.entries(executions).flatMap(([workflowId, list]) => list.map((e) => ({ workflowId, e })));
  const stamp = (e: WorkflowExecutionResponse) => new Date(e.started_at ?? e.created_at).getTime();
  const week = runs.filter(({ e }) => now.getTime() - stamp(e) <= WEEK && e.status !== "running");
  const failed = week.filter(({ e }) => e.status === "failed");
  const ok = week.filter(({ e }) => e.status === "completed");
  const running = runs.filter(({ e }) => e.status === "running");
  const latestFailed = Object.entries(executions)
    .map(([workflowId, list]) => ({ workflowId, e: list[0] }))
    .filter(({ e }) => e?.status === "failed");

  useScreenPublisher({
    focused_module: "doing-now",
    visible: [
      ...active.map((g) => ({ kind: "goal", id: g.id }) as WsScreenRef),
      ...running.map(({ workflowId, e }) => ({ kind: "workflow_execution", id: e.id, parent_id: workflowId }) as WsScreenRef),
    ].slice(0, 10),
  });

  return (
    <Module label="Doing now" className="world-doing">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read what Ze is doing.
        </p>
      ) : loading ? (
        <p className="muted">Reading…</p>
      ) : (
        <>
          {active.length === 0 && (
            <div className="row">
              <span className="t muted">No goal running</span>
            </div>
          )}
          {active.map((g) => (
            <div key={g.id} className="row">
              <span className="t">{g.title}</span>
              <span className="ro on">
                {g.milestones_done}/{g.milestones_total}
              </span>
              <span className="s">
                {g.stuck_since ? `Stuck since ${relDay(new Date(g.stuck_since), now)}` : g.gate_id ? "Waiting on your OK" : g.next_milestone ? `Next: ${g.next_milestone}` : g.status === "paused" ? "Paused" : "In progress"}
              </span>
            </div>
          ))}
          {running.map(({ workflowId, e }) => (
            <div key={e.id} className="row">
              <span className="t">{nameOf(workflowId)}</span>
              <span className="lbl on">running</span>
            </div>
          ))}
          {next ? (
            <div className="row">
              <span className="t">{next.name}</span>
              <span className="ro">
                {relDay(new Date(next.next_run_at!), now)} {hhmm(new Date(next.next_run_at!))}
              </span>
              <span className="s">Next run</span>
            </div>
          ) : (
            <div className="row">
              <span className="t muted">No workflow due</span>
            </div>
          )}
          <div className="row">
            <span className="t">Runs · 7 d</span>
            <span className={`lbl ${failed.length ? "hot" : ""}`}>
              {ok.length} ok · {failed.length} failed
            </span>
          </div>
          {latestFailed.map(({ workflowId, e }) => (
            <div key={e.id} className="row hot">
              <span className="t">{nameOf(workflowId)} failed</span>
              <span className="s">{e.failure_summary ?? "The run did not finish."}</span>
            </div>
          ))}
        </>
      )}
    </Module>
  );
}
