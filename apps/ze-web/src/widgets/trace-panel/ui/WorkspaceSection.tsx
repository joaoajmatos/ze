import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { TraceSection } from "@/widgets/message-trace/ui/TraceSection";

type WorkspaceTrace = NonNullable<
  (WsTraceUpdateFrame & {
    workspace?: {
      mode: string;
      runs?: { command?: string; status?: string }[];
      files?: { path: string; op?: string }[];
      script_ran?: boolean;
      unavailable?: boolean;
      planned?: string[] | null;
    } | null;
  })["workspace"]
>;

interface WorkspaceSectionProps {
  workspace: WorkspaceTrace | null | undefined;
  live?: boolean;
}

export function WorkspaceSection({ workspace, live }: WorkspaceSectionProps) {
  const files = workspace?.files ?? [];
  const runs = workspace?.runs ?? [];
  const planned = workspace?.planned ?? [];
  const count = files.length + runs.length + planned.length;
  return (
    <TraceSection title="Workspace" count={workspace ? Math.max(count, 1) : 0} loading={live && !workspace}>
      {!workspace ? (
        <p className="text-xs text-smoke/80 italic">No workspace use</p>
      ) : (
        <div className="space-y-1.5 text-xs">
          <p className="text-foreground/90">
            Mode {workspace.mode}
            {workspace.unavailable ? " · unavailable" : ""}
            {workspace.script_ran ? " · script ran" : ""}
          </p>
          {planned.map((item) => (
            <p key={item} className="text-smoke">
              {item}
            </p>
          ))}
          {runs.map((run, i) => (
            <p
              key={`${run.command ?? "run"}-${i}`}
              className="font-mono text-foreground/80"
              data-testid={run.status === "in_progress" ? "workspace-run-in-progress" : undefined}
            >
              $ {run.command}
              {run.status === "in_progress" ? (
                <span className="ml-1.5 rounded bg-amber-spark/20 px-1 py-0.5 font-sans text-[10px] uppercase tracking-wide text-amber-spark">
                  still running
                </span>
              ) : null}
            </p>
          ))}
          {files.map((file) => (
            <p key={`${file.op}-${file.path}`} className="text-smoke">
              {file.op ?? "file"} {file.path}
            </p>
          ))}
        </div>
      )}
    </TraceSection>
  );
}
