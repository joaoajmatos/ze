import type { WorkspaceUsageTraceResponse } from "@myguyze/ze-client";
import { TraceRow } from "./TraceRow";

export function WorkspaceRow({ workspace, live }: { workspace: WorkspaceUsageTraceResponse | null | undefined; live?: boolean }) {
  const files = workspace?.files ?? [];
  const runs = workspace?.runs ?? [];
  const planned = workspace?.planned ?? [];
  const count = files.length + runs.length + planned.length;
  return (
    <TraceRow title="Workspace" count={workspace ? Math.max(count, 1) : 0} loading={live && !workspace}>
      {!workspace ? (
        <p className="muted">No workspace use</p>
      ) : (
        <div className="tr-list">
          <p className="key">
            {workspace.unavailable ? "Unavailable" : "Used"}
            {workspace.script_ran ? " · script ran" : ""}
          </p>
          {planned.map((item) => (
            <p key={item} className="muted">
              {item}
            </p>
          ))}
          {runs.map((run, i) => (
            <p key={`${run.command}-${i}`} className="ro" data-testid={run.status === "in_progress" ? "workspace-run-in-progress" : undefined}>
              $ {run.command}
              {run.status === "in_progress" ? <span className="chip solid">still running</span> : null}
            </p>
          ))}
          {files.map((file) => (
            <p key={`${file.op}-${file.path}`} className="muted">
              {file.op} {file.path}
            </p>
          ))}
        </div>
      )}
    </TraceRow>
  );
}
