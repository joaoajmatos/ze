import { useWorkspaceFilesQuery, useWorkspaceQuery } from "@/entities/workspace";
import { RedirectHintTarget } from "@/shared/ui";
import { Module } from "@/shared/ui/hud";
import { formatBytes, formatMtime } from "../lib/format";

/** Governance › Files: a read-only map of Ze's workspace (status and tree; uploads stay in chat). */
export function Files() {
  const status = useWorkspaceQuery();
  const files = useWorkspaceFilesQuery();
  const label = "What is in Ze's workspace?";
  const failed = status.isError || files.isError;
  const off = status.data && !status.data.available;

  return (
    <RedirectHintTarget hintId="files">
      <Module label={label}>
        <div className="gov-stack">
          {failed ? (
            <p className="gov-err">
              Could not load workspace files.{" "}
              <button
                type="button"
                className="ctl-text"
                onClick={() => {
                  void status.refetch();
                  void files.refetch();
                }}
              >
                Retry
              </button>
            </p>
          ) : off ? (
            <p className="gov-note">Workspace is off</p>
          ) : (
            <>
              {status.data && (
                <p className="ro">
                  {formatBytes(status.data.bytes_used)} of {formatBytes(status.data.bytes_ceiling)}
                  {status.data.busy ? " · busy" : ""}
                </p>
              )}
              {files.data && files.data.length === 0 && <p className="gov-note">No files yet</p>}
              {files.data && files.data.length > 0 && (
                <ul aria-label="Workspace files" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {files.data.map((f) => (
                    <li key={f.path} className="row gov-file-row">
                      <span className="t">{f.path}</span>
                      <span className="ro">{f.is_dir ? "folder" : formatBytes(f.size)}</span>
                      <span className="s">{formatMtime(f.modified_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
              {!status.data && !files.data && <p className="gov-note">Loading…</p>}
            </>
          )}
        </div>
      </Module>
    </RedirectHintTarget>
  );
}
