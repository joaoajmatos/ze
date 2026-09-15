import { ApiError } from "@myguyze/ze-client";
import { useCancelWorkspaceRunMutation, useWorkspaceRunEventsQuery } from "@/entities/workspace";
import type { WorkspaceRunItem } from "@/entities/workspace";
import { Button } from "@/shared/ui";

function LiveRunOutput({ runId }: { runId: string }) {
  const { lines, looksBinary } = useWorkspaceRunEventsQuery(runId);
  if (!lines) return null;
  if (looksBinary) {
    return (
      <p className="mt-1 text-[11px] italic text-smoke">
        output is not printable — retrieve it from the workspace file
      </p>
    );
  }
  return (
    <pre
      data-testid="workspace-run-live-output"
      className="mt-1 max-h-40 w-full overflow-y-auto whitespace-pre-wrap rounded-lg bg-foreground/5 p-2 text-[11px] font-mono text-smoke"
    >
      {lines}
    </pre>
  );
}

function formatStartedAt(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function RunningRunBanner({ runs }: { runs: WorkspaceRunItem[] }) {
  const inProgress = runs.filter((run) => run.ended_at === null);
  const cancelRun = useCancelWorkspaceRunMutation();
  if (inProgress.length === 0) return null;

  return (
    <div
      data-testid="running-run-banner"
      className="space-y-2 rounded-lg border border-amber-spark/40 bg-amber-spark/10 p-4"
    >
      {inProgress.map((run) => {
        const isCancellingThis =
          cancelRun.isPending && cancelRun.variables === run.id;
        const cancelFailedThis =
          cancelRun.isError && cancelRun.variables === run.id;
        return (
          <div key={run.id ?? run.command} className="flex flex-col">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <span className="h-2 w-2 flex-shrink-0 animate-pulse rounded-full bg-amber-spark" />
                <p className="min-w-0 truncate text-sm text-foreground">
                  <span className="font-mono">{run.command}</span> is still running
                  {run.started_at ? ` · started ${formatStartedAt(run.started_at)}` : ""}
                </p>
              </div>
              <div className="flex flex-shrink-0 items-center gap-2">
                {cancelFailedThis && (
                  <span data-testid="cancel-run-error" className="text-xs text-red-400">
                    {cancelRun.error instanceof ApiError && cancelRun.error.status === 409
                      ? "already finished"
                      : "couldn't stop it"}
                  </span>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  data-testid="cancel-run-button"
                  disabled={!run.id || cancelRun.isPending}
                  onClick={() => run.id && cancelRun.mutate(run.id)}
                >
                  {isCancellingThis ? "Stopping…" : "Stop"}
                </Button>
              </div>
            </div>
            {run.id && <LiveRunOutput runId={run.id} />}
          </div>
        );
      })}
    </div>
  );
}
