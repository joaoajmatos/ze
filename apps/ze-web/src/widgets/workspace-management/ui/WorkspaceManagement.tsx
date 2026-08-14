import { FolderOpen } from "lucide-react";
import { useRef, useState } from "react";
import {
  retrieveWorkspaceFile,
  useWorkspaceFilesQuery,
  useWorkspaceModeMutation,
  useWorkspaceQuery,
  useWorkspaceResetMutation,
  useWorkspaceRunsQuery,
  useWorkspaceUploadMutation,
  type WorkspaceMode,
} from "@/entities/workspace";
import { Button, ListPage, SectionPanel } from "@/shared/ui";
import { formatBytes, formatMtime } from "../lib/format";
import { WorkspaceModeSwitcher } from "./WorkspaceModeSwitcher";

export function WorkspaceManagement() {
  const status = useWorkspaceQuery();
  const files = useWorkspaceFilesQuery();
  const runs = useWorkspaceRunsQuery();
  const setMode = useWorkspaceModeMutation();
  const upload = useWorkspaceUploadMutation();
  const reset = useWorkspaceResetMutation();
  const fileInput = useRef<HTMLInputElement>(null);
  const [pendingResetId, setPendingResetId] = useState<string | null>(null);

  const isLoading = status.isLoading || files.isLoading;
  const isError = status.isError || files.isError;

  async function onUpload(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    upload.mutate(file);
    if (fileInput.current) fileInput.current.value = "";
  }

  async function onRetrieve(path: string) {
    const blob = await retrieveWorkspaceFile(path);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = path.split("/").pop() || path;
    a.click();
    URL.revokeObjectURL(url);
  }

  function onResetClick() {
    reset.mutate(undefined, {
      onSuccess: (data) => {
        if (data.confirmation_id) setPendingResetId(data.confirmation_id);
      },
    });
  }

  function resolveReset(choice: "approve" | "deny") {
    if (!pendingResetId) return;
    reset.mutate(
      { confirmationId: pendingResetId, choice },
      { onSettled: () => setPendingResetId(null) },
    );
  }

  const mode: WorkspaceMode = status.data?.mode ?? "ask";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <WorkspaceModeSwitcher
          mode={mode}
          disabled={setMode.isPending}
          onChange={(next) => setMode.mutate(next)}
        />
        <div className="flex items-center gap-2">
          <input
            ref={fileInput}
            type="file"
            className="hidden"
            onChange={(e) => void onUpload(e.target.files)}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={upload.isPending}
            onClick={() => fileInput.current?.click()}
          >
            Upload
          </Button>
          <Button
            size="sm"
            variant="danger"
            disabled={reset.isPending}
            onClick={onResetClick}
          >
            Reset
          </Button>
        </div>
      </div>

      {pendingResetId && (
        <div className="rounded-lg border border-amber-spark/40 bg-amber-spark/10 p-4">
          <p className="text-sm text-white mb-3">
            Reset the workspace? All files will be removed.
          </p>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => resolveReset("approve")}>
              Confirm reset
            </Button>
            <Button size="sm" variant="ghost" onClick={() => resolveReset("deny")}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {status.data && (
        <p className="text-xs text-smoke">
          {status.data.available ? "Sidecar available" : "Sidecar unavailable"} ·{" "}
          {formatBytes(status.data.bytes_used)} / {formatBytes(status.data.bytes_ceiling)}
          {status.data.busy ? " · busy" : ""}
        </p>
      )}

      <ListPage
        isLoading={isLoading}
        isError={isError}
        isEmpty={!files.data?.length}
        emptyIcon={FolderOpen}
        emptyMessage="Workspace is empty."
        errorMessage="Could not load workspace files."
        onRetry={() => {
          void status.refetch();
          void files.refetch();
        }}
        className="space-y-2 px-0 py-0"
      >
        <div className="space-y-2">
          {files.data?.map((file) => (
            <div
              key={file.path}
              className="flex items-center justify-between gap-4 rounded-lg border border-white/10 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{file.path}</p>
                <p className="text-xs text-smoke">
                  {formatBytes(file.size)} · {formatMtime(file.modified_at)}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void onRetrieve(file.path)}
              >
                Retrieve
              </Button>
            </div>
          ))}
        </div>
      </ListPage>

      <SectionPanel>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-smoke">
          Recent activity
        </h2>
        {runs.data?.length ? (
          <ul className="space-y-2">
            {runs.data.map((run) => (
              <li key={run.id ?? `${run.command}-${run.started_at}`} className="text-xs text-smoke">
                <span className="font-mono text-white/90">{run.command}</span>
                {" · "}
                <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-white/80">
                  {run.origin}
                </span>
                {" · "}
                {run.status}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-smoke/80 italic">No runs yet</p>
        )}
      </SectionPanel>
    </div>
  );
}
