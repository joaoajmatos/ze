import type { WorkspaceRunItem } from "@/entities/workspace";

function formatStartedAt(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function RunningRunBanner({ runs }: { runs: WorkspaceRunItem[] }) {
  const inProgress = runs.filter((run) => run.ended_at === null);
  if (inProgress.length === 0) return null;

  return (
    <div
      data-testid="running-run-banner"
      className="space-y-2 rounded-lg border border-amber-spark/40 bg-amber-spark/10 p-4"
    >
      {inProgress.map((run) => (
        <div
          key={run.id ?? run.command}
          className="flex flex-wrap items-center justify-between gap-2"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="h-2 w-2 flex-shrink-0 animate-pulse rounded-full bg-amber-spark" />
            <p className="min-w-0 truncate text-sm text-white">
              <span className="font-mono">{run.command}</span> is still running
              {run.started_at ? ` · started ${formatStartedAt(run.started_at)}` : ""}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
