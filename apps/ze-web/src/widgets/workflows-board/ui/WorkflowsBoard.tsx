import type { WorkflowExecutionResponse, WorkflowResponse, WsScreenRef } from "@myguyze/ze-client";
import { Link } from "react-router-dom";
import { formatSchedule, lastResult, untilPhrase, useTriggerWorkflowMutation } from "@/entities/workflow";
import { workflowPath } from "@/shared/config";
import { ago } from "@/shared/lib";
import { ChatAboutChip, Module } from "@/shared/ui";

interface Props {
  workflows: WorkflowResponse[];
  executions: Record<string, WorkflowExecutionResponse[]>;
  loading: boolean;
  error: boolean;
  offline: boolean;
  now: Date;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

/** Every execution runs unattended, so a failed one is coral however it started. */
export function WorkflowsBoard({ workflows, executions, loading, error, offline, now, onChatAbout }: Props) {
  const trigger = useTriggerWorkflowMutation();

  return (
    <Module label="Workflows" className="doing-workflows">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read your workflows.
        </p>
      ) : loading ? (
        <p className="muted" role="status">
          Reading…
        </p>
      ) : workflows.length === 0 ? (
        <p className="muted">No workflows yet. Ask Ze to set one up.</p>
      ) : (
        <ul className="doing-list">
          {workflows.map((w) => {
            const result = lastResult(executions[w.id]);
            const running = trigger.isPending && trigger.variables === w.id;
            const ref = { kind: "workflow", id: w.id } as WsScreenRef;
            return (
              <li key={w.id} className={`row ${result.kind === "failed" ? "hot" : ""}`} data-workflow={w.id}>
                <Link className="t goal-link" to={workflowPath(w.id)}>
                  {w.name}
                </Link>
                <span className="lbl">{w.enabled ? "On" : "Off"}</span>
                <span className="s">
                  {formatSchedule(w.schedule)}
                  {w.next_run_at ? ` · next ${untilPhrase(w.next_run_at, now)}` : ""}
                </span>
                <span className="s">
                  {result.kind === "unknown" && "—"}
                  {result.kind === "never" && "Never run"}
                  {result.kind === "running" && "Running"}
                  {result.kind === "ok" && `Last run went fine${w.last_run_at ? ` · ${ago(new Date(w.last_run_at), now)}` : ""}`}
                  {result.kind === "cancelled" && "Last run was cancelled"}
                  {result.kind === "held" && "Waiting on a write you have not approved"}
                  {result.kind === "other" && `Last run: ${result.text}`}
                  {result.kind === "failed" && `Last run failed: ${result.text}`}
                </span>
                <span className="acts">
                  <button type="button" className="ctl" disabled={offline || running || result.kind === "running"} onClick={() => trigger.mutate(w.id)}>
                    {running ? "Starting…" : "Run now"}
                  </button>
                  <Link className="ctl" to={workflowPath(w.id)}>
                    Open
                  </Link>
                </span>
                {onChatAbout && <ChatAboutChip label={w.name} onClick={(chip) => onChatAbout(ref, chip.closest(".row"))} />}
              </li>
            );
          })}
        </ul>
      )}
      {trigger.isError && (
        <p className="hot" role="alert">
          That didn't start. Try again.
        </p>
      )}
    </Module>
  );
}
