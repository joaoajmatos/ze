import type { WorkspaceRunResponse, WorkspaceStatusResponse, WsScreenRef } from "@myguyze/ze-client";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { isAlarm, originWord, runStatusWord, useCancelWorkspaceRunMutation, useWorkspaceRunEventsQuery } from "@/entities/workspace";
import { ago, queryKeys } from "@/shared/lib";
import { ChatAboutChip, Module } from "@/shared/ui";

interface Props {
  runs: WorkspaceRunResponse[];
  loading: boolean;
  error: boolean;
  workspace: WorkspaceStatusResponse | undefined;
  now: Date;
  offline: boolean;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

function RunRow({ run, now, offline, onChatAbout }: { run: WorkspaceRunResponse; now: Date; offline: boolean; onChatAbout?: Props["onChatAbout"] }) {
  const queryClient = useQueryClient();
  const cancel = useCancelWorkspaceRunMutation();
  const [line, setLine] = useState<string | null>(null);
  const running = run.status === "in_progress";
  const live = useWorkspaceRunEventsQuery(running ? run.id : null);

  // The backend sends no refresh frame for the workspace, so the end of the stream is the signal.
  useEffect(() => {
    if (live.status !== "closed") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.workspaceRuns() });
    void queryClient.invalidateQueries({ queryKey: queryKeys.workspace() });
  }, [live.status, queryClient]);

  const alarm = isAlarm(run);
  const output = running && live.lines ? live.lines : run.output_preview;
  const done = !running && run.status !== "refused";
  const started = run.started_at ? ago(new Date(run.started_at), now) : "not started";

  return (
    <li className={`row ${alarm ? "hot" : ""}`} data-run={run.id ?? "none"}>
      <code className="t run-command">{run.command}</code>
      <span className="lbl">{runStatusWord(run.status)}</span>
      <span className="s">
        {originWord(run.origin)} · {started}
        {done && run.exit_code !== null ? ` · exit ${run.exit_code}` : ""}
      </span>
      {run.error_summary && <span className="s">{run.error_summary}</span>}
      {output && (live.looksBinary && running ? <span className="s">binary output</span> : <pre className="run-output">{output}</pre>)}
      {running && run.id && (
        <span className="acts">
          <button
            type="button"
            className="ctl"
            disabled={offline || cancel.isPending}
            onClick={() =>
              cancel.mutate(run.id!, { onSuccess: (r) => setLine(r.outcome === "gone" ? `This run ${r.line}.` : null) })
            }
          >
            Cancel
          </button>
        </span>
      )}
      {line && <span className="s" role="status">{line}</span>}
      {cancel.isError && (
        <span className="hot" role="alert">
          Couldn't cancel that run.
        </span>
      )}
      {onChatAbout && run.id && (
        <ChatAboutChip label={run.command} onClick={(chip) => onChatAbout({ kind: "workspace_run", id: run.id! } as WsScreenRef, chip.closest(".row"))} />
      )}
    </li>
  );
}

export function Runs({ runs, loading, error, workspace, now, offline, onChatAbout }: Props) {
  const off = workspace?.available === false;
  return (
    <Module label="Runs" className="doing-runs">
      {off ? (
        <p className="hot" role="alert">
          Workspace is off.
        </p>
      ) : error ? (
        <p className="hot" role="alert">
          Couldn't read your runs.
        </p>
      ) : loading ? (
        <p className="muted" role="status">
          Reading…
        </p>
      ) : (
        <>
          {workspace?.busy && <p className="s">busy · one run at a time</p>}
          {runs.length === 0 ? (
            <p className="muted">No runs yet. Ask Ze to run something in its workspace.</p>
          ) : (
            <ul className="doing-list">
              {runs.map((r, i) => (
                <RunRow key={r.id ?? `n${i}`} run={r} now={now} offline={offline} onChatAbout={onChatAbout} />
              ))}
            </ul>
          )}
        </>
      )}
    </Module>
  );
}
