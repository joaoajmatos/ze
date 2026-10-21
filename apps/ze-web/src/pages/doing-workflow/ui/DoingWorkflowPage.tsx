import type { WorkflowExecutionResponse, WorkflowRevisionResponse, WorkflowStepResponse, WsScreenRef } from "@myguyze/ze-client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { PluginModuleSlot } from "@/widgets/plugin-module";
import { WorkflowGraph } from "@/widgets/workflow-graph";
import { useChatAbout } from "@/features/ask-bar";
import { useScreenPublisher } from "@/entities/screen-context";
import { useSession } from "@/entities/session";
import {
  averageSuccessfulRunDuration,
  formatDurationMs,
  formatSchedule,
  useCancelExecutionMutation,
  useLiveExecutionQuery,
  useTriggerWorkflowMutation,
  useWorkflowDetailQuery,
  useWorkflowExecutionsQuery,
  useWorkflowRevisionsQuery,
  executionDurationMs,
} from "@/entities/workflow";
import { askPath, workflowsPath } from "@/shared/config";
import { agoPhrase, humanizeStatus, useSetBreadcrumbTitle } from "@/shared/lib";
import { Chip, Module } from "@/shared/ui";

const dateTime = (iso: string) => new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

const STATUS_WORD: Record<string, string> = { completed: "Completed", failed: "Failed", running: "Running", cancelled: "Cancelled" };
const statusWord = (s: string) => STATUS_WORD[s] ?? humanizeStatus(s);

function executionRef(execution: WorkflowExecutionResponse): WsScreenRef {
  return {
    kind: "workflow_execution",
    id: execution.id,
    parent_id: execution.workflow_id ?? undefined,
    label: execution.started_at ? `Run of ${dateTime(execution.started_at)}` : "Workflow run",
    component: "execution_row",
    as_of: execution.completed_at ?? execution.started_at ?? execution.created_at,
  } as WsScreenRef;
}

function graphSteps(execution: WorkflowExecutionResponse | null | undefined, current: WorkflowStepResponse[]): WorkflowStepResponse[] {
  const snapshot = execution?.steps_snapshot ?? [];
  return snapshot.length > 0 ? snapshot : current;
}

export function DoingWorkflowPage() {
  const { workflowId = "" } = useParams<{ workflowId: string }>();
  const [liveId, setLiveId] = useState<string | null>(null);
  const [selected, setSelected] = useState<WorkflowExecutionResponse | null>(null);
  const detailQ = useWorkflowDetailQuery(workflowId);
  const execQ = useWorkflowExecutionsQuery(workflowId);
  const revQ = useWorkflowRevisionsQuery(workflowId);
  const { data: live } = useLiveExecutionQuery(workflowId, liveId);
  const trigger = useTriggerWorkflowMutation();
  const cancel = useCancelExecutionMutation();
  const chatAbout = useChatAbout();
  const detail = detailQ.data;
  const executions = execQ.data;

  const [params] = useSearchParams();
  const requested = params.get("execution");
  const [applied, setApplied] = useState<string | null>(null);
  if (requested && applied !== requested && executions) {
    const match = executions.find((e) => e.id === requested);
    if (match) {
      setApplied(requested);
      setSelected(match);
    }
  }

  useSetBreadcrumbTitle(detail?.name);
  useScreenPublisher(
    detail
      ? {
          subject: [
            { kind: "workflow", id: detail.id, label: detail.name, component: "workflow_module" },
            ...(requested && selected?.id === requested ? [executionRef(selected)] : []),
          ],
          focused_module: "Workflows",
        }
      : null,
  );

  const display = selected ?? live;
  const running = trigger.isPending || live?.status === "running" || display?.status === "running";
  const activeId = liveId ?? (live?.status === "running" ? live.id : null);
  const avg = executions ? averageSuccessfulRunDuration(executions) : null;

  if (detailQ.isLoading) {
    return (
      <p className="muted" role="status">
        Reading…
      </p>
    );
  }
  if (detailQ.isError || !detail) {
    return (
      <div className="doing-detail">
        <Link className="back-link" to={workflowsPath()}>
          ← Doing
        </Link>
        <p className="hot" role="alert">
          Couldn't load this workflow.
        </p>
        <button type="button" className="ctl" onClick={() => void detailQ.refetch()}>
          Retry
        </button>
      </div>
    );
  }

  const wfRef = { kind: "workflow", id: detail.id, label: detail.name, component: "workflow_module" } as WsScreenRef;
  const failed = display && display.status === "failed";

  return (
    <div className="doing-detail">
      <Link className="back-link" to={workflowsPath()}>
        ← Doing
      </Link>

      <Module as="div" label="Workflow" chatAboutLabel={detail.name} onChatAbout={(el) => chatAbout(wfRef, el)}>
        <h1 className="t">{detail.name}</h1>
        {detail.description && <p className="s">{detail.description}</p>}
        <p className="doing-detail-head">
          <Chip>{detail.enabled ? "On" : "Off"}</Chip>
          <Chip>{formatSchedule(detail.schedule)}</Chip>
          {avg && <Chip>{avg} average run</Chip>}
        </p>
        {detail.enabled && (
          <p className="acts">
            {running && activeId && (
              <button type="button" className="ctl" disabled={cancel.isPending} onClick={() => cancel.mutate({ workflowId, executionId: activeId })}>
                {cancel.isPending ? "Cancelling…" : "Cancel"}
              </button>
            )}
            <button
              type="button"
              className="ctl"
              disabled={running}
              onClick={() => {
                setSelected(null);
                trigger.mutate(workflowId, { onSuccess: (d) => setLiveId(d.execution_id) });
              }}
            >
              {trigger.isPending ? "Starting…" : "Run now"}
            </button>
          </p>
        )}
        {(trigger.isError || cancel.isError) && (
          <p className="hot" role="alert">
            That didn't go through. Try again.
          </p>
        )}
      </Module>

      <Module as="div" label="Steps" tone={failed ? "hot" : "default"}>
        <p className="s">
          {running ? "Running…" : display ? `${statusWord(display.status)}${display.started_at ? ` · ${dateTime(display.started_at)}` : ""}` : "Current steps"}
          {display && !running && (
            <>
              {" "}
              <button
                type="button"
                className="ctl"
                onClick={() => {
                  setLiveId(null);
                  setSelected(null);
                }}
              >
                Clear
              </button>{" "}
              <button type="button" className="ctl" onClick={(e) => chatAbout(executionRef(display), e.currentTarget)}>
                Chat about this run
              </button>
            </>
          )}
        </p>
        <WorkflowGraph steps={graphSteps(display, detail.steps)} execution={display} isLive={running} />
        {failed && display.failure_summary && <p className="hot">{display.failure_summary}</p>}
        {display?.summary && display.status !== "running" && (
          <div className="step-output">
            <ReactMarkdown>{display.summary}</ReactMarkdown>
          </div>
        )}
      </Module>

      {display && <PluginModuleSlot slot="doing.run" subject={{ kind: "workflow_run", id: display.id, parent_id: workflowId }} />}

      <Module as="div" label="Runs">
        {execQ.isError ? (
          <p className="hot" role="alert">
            Couldn't read the runs.
          </p>
        ) : execQ.isLoading ? (
          <p className="muted" role="status">
            Reading…
          </p>
        ) : (executions ?? []).length === 0 ? (
          <p className="muted">Never run.</p>
        ) : (
          <ul className="doing-list">
            {executions!.map((ex) => {
              const ms = executionDurationMs(ex.started_at, ex.completed_at);
              const bad = ex.status === "failed";
              return (
                <li key={ex.id} className={`row ${bad ? "hot" : ""} ${ex.id === display?.id ? "selected" : ""}`}>
                  <button type="button" className="ctl-text entity-hit" aria-pressed={ex.id === display?.id} onClick={() => setSelected(ex)}>
                    <span className="t">{statusWord(ex.status)}</span>
                    <span className="s">
                      {ex.started_at ? dateTime(ex.started_at) : "not started"}
                      {ms !== null ? ` · ${formatDurationMs(ms)}` : ""}
                      {ex.status !== "running" ? ` · ${ex.step_results.length} ${ex.step_results.length === 1 ? "step" : "steps"}` : ""}
                    </span>
                  </button>
                  {bad && <span className="s">{ex.failure_summary ?? "Failed"}</span>}
                </li>
              );
            })}
          </ul>
        )}
      </Module>

      <Module as="div" label="Changes">
        {revQ.isError ? (
          <p className="hot" role="alert">
            Couldn't read the change history.
          </p>
        ) : revQ.isLoading ? (
          <p className="muted" role="status">
            Reading…
          </p>
        ) : (revQ.data ?? []).length === 0 ? (
          <p className="muted">No changes recorded yet. Edits made before this was tracked aren't shown here.</p>
        ) : (
          <ul className="doing-list">
            {revQ.data!.map((r) => (
              <RevisionRow key={r.id} revision={r} />
            ))}
          </ul>
        )}
      </Module>
    </div>
  );
}

function RevisionRow({ revision }: { revision: WorkflowRevisionResponse }) {
  const [open, setOpen] = useState(false);
  const [gone, setGone] = useState(false);
  const navigate = useNavigate();
  const now = new Date();

  function viewConversation() {
    if (!revision.actor_session_id) {
      setGone(true);
      return;
    }
    useSession.getState().selectSession(revision.actor_session_id);
    useSession.getState().setHighlightMessage(revision.actor_user_message_id ?? null);
    navigate(askPath(revision.actor_session_id));
  }

  return (
    <li className="row">
      <button type="button" className="ctl-text entity-hit" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="t">{revision.summary || "No fields changed"}</span>
        <span className="s">
          #{revision.revision_number} · {revision.change_type === "created" ? "Created" : "Edited"} · {revision.actor_source === "api" ? "API" : "Ze"} · {agoPhrase(new Date(revision.created_at), now)}
        </span>
      </button>
      {revision.actor_source === "agent" && (
        <span className="acts">
          {gone ? (
            <span className="s">Conversation unavailable.</span>
          ) : (
            <button type="button" className="ctl" onClick={viewConversation}>
              View conversation
            </button>
          )}
        </span>
      )}
      {open && (
        <div className="s">
          <h3 className="lbl">Before</h3>
          <StepList steps={revision.steps_before} />
          <h3 className="lbl">After</h3>
          <StepList steps={revision.steps_after} />
        </div>
      )}
    </li>
  );
}

function StepList({ steps }: { steps: WorkflowStepResponse[] }) {
  if (steps.length === 0) return <p className="muted">(none)</p>;
  return (
    <ul>
      {steps.map((s) => (
        <li key={s.id}>
          {s.task}
          {s.on_failure && s.on_failure !== "fail" && ` (if it fails: ${humanizeStatus(s.on_failure)})`}
        </li>
      ))}
    </ul>
  );
}
