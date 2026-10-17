import { useState } from "react";
import { useDeleteUserData } from "@/features/delete-user-data";
import { useExportUserData } from "@/features/export-user-data";
import { useImportUserData } from "@/features/import-user-data";
import { useDataDomainsQuery } from "@/entities/data-domain";
import { settingsDataSectionId } from "@/shared/config";
import { RedirectHintTarget } from "@/shared/ui";
import { Control, Module } from "@/shared/ui/hud";
import { domainLabel } from "../lib/domain-labels";

const DELETE_LIST = ["Memories, facts and episodes", "Goals and milestones", "Contacts", "Messages and conversation history", "Reminders", "Usage history"];

/** Governance › Data: what Ze holds, and how to take it out or erase it. */
export function Data() {
  const domains = useDataDomainsQuery();
  const { exporting, exportError, exportData } = useExportUserData();
  const { importing, importResult, importError, importData, importInputRef, openImportDialog } = useImportUserData();
  const { deleting, deleteError, deleteAllData, clearDeleteError } = useDeleteUserData();
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const label = "What does Ze hold, and can I take it?";

  function openDelete() {
    setTyped("");
    clearDeleteError();
    setConfirming(true);
  }

  return (
    <RedirectHintTarget hintId={settingsDataSectionId}>
      <Module label={label}>
        <div className="gov-stack">
          {domains.isError ? (
            <p className="gov-err">
              Could not load your data.{" "}
              <button type="button" className="ctl-text" onClick={() => void domains.refetch()}>
                Retry
              </button>
            </p>
          ) : domains.data ? (
            <ul aria-label="Data held" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {domains.data.domains.map((d) => (
                <li key={d.name} className="row gov-row">
                  <span className="t">{domainLabel(d.name)}</span>
                  <span className="ro">{d.count === null ? "—" : d.count.toLocaleString()}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="gov-note">Loading…</p>
          )}

          <div className="gov-actions">
            <Control onClick={() => void exportData()} disabled={exporting}>
              {exporting ? "Preparing export" : "Export your data"}
            </Control>
            <input ref={importInputRef} type="file" accept=".zip" hidden onChange={(e) => void importData(e)} />
            <Control onClick={openImportDialog} disabled={importing}>
              {importing ? "Importing" : "Import data"}
            </Control>
          </div>
          {(exporting || importing) && <div className="gov-rule" role="progressbar" aria-label={exporting ? "Preparing export" : "Importing"} />}
          {exportError && <p className="gov-err">{exportError}</p>}
          {importError && <p className="gov-err">{importError}</p>}
          {importResult && (
            <p className="gov-ok">
              Imported {importResult.domains_imported.length} domains ({Object.values(importResult.rows_imported).reduce((a, b) => a + b, 0)} rows).
            </p>
          )}

          <div>
            <Control className="hot" onClick={openDelete}>
              Delete all data
            </Control>
          </div>
        </div>
      </Module>

      {confirming && (
        <div className="gov-dialog" role="dialog" aria-modal="true" aria-labelledby="gov-delete-title">
          <div className="gov-dialog-box hot">
            <div>
              <h3 id="gov-delete-title" className="sentence" style={{ margin: 0 }}>
                Delete all data?
              </h3>
              <p className="gov-err">This cannot be undone.</p>
            </div>
            <ul className="gov-note" style={{ margin: 0, paddingLeft: 18 }}>
              {DELETE_LIST.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="gov-field">
              <label className="lbl" htmlFor="gov-delete-confirm">
                Type DELETE to confirm
              </label>
              <input id="gov-delete-confirm" className="gov-in" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="DELETE" autoFocus />
            </div>
            {deleteError && <p className="gov-err">{deleteError}</p>}
            <div className="gov-actions">
              <Control onClick={() => setConfirming(false)} disabled={deleting}>
                Cancel
              </Control>
              <Control className="hot" onClick={() => void deleteAllData()} disabled={typed !== "DELETE" || deleting}>
                {deleting ? "Deleting" : "Delete everything"}
              </Control>
            </div>
          </div>
        </div>
      )}
    </RedirectHintTarget>
  );
}
