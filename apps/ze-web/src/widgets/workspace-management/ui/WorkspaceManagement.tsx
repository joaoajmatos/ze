import { FolderOpen } from "lucide-react";
import { useWorkspaceFilesQuery, useWorkspaceQuery } from "@/entities/workspace";
import { ListPage } from "@/shared/ui";
import { formatBytes, formatMtime } from "../lib/format";

export function WorkspaceManagement() {
  const status = useWorkspaceQuery();
  const files = useWorkspaceFilesQuery();

  const isLoading = status.isLoading || files.isLoading;
  const isError = status.isError || files.isError;

  return (
    <div className="space-y-6">
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
              className="flex items-center justify-between gap-4 rounded-lg border border-foreground/10 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{file.path}</p>
                <p className="text-xs text-smoke">
                  {formatBytes(file.size)} · {formatMtime(file.modified_at)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </ListPage>
    </div>
  );
}
