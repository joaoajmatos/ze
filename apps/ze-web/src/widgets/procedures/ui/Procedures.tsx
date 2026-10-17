import { useState } from "react";
import { ProcedureControls } from "@/features/procedure-review";
import { ReviewProcedureCandidate } from "@/features/review-procedure";
import { useProcedureCandidatesQuery, useProcedureDetailQuery, useProcedureLibraryQuery } from "@/entities/procedure";
import { Chip, Control, Module } from "@/shared/ui";

const STATUS_WORDS: Record<string, string> = { active: "active", retired: "disabled" };
const status = (s: string) => STATUS_WORDS[s] ?? s.replace(/_/g, " ");

interface ProceduresProps {
  onChatAbout?: (element: Element) => void;
  /** Called with a procedure id when its row asks for "Chat about this". */
  onChatAboutProcedure?: (procedure: { id: string; name: string }, element: Element) => void;
}

export function Procedures({ onChatAbout, onChatAboutProcedure }: ProceduresProps) {
  const candidates = useProcedureCandidatesQuery();
  const library = useProcedureLibraryQuery();
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const selected = useProcedureDetailQuery(selectedId).data;
  const waiting = candidates.data ?? [];
  const rows = library.data ?? [];
  const nothing = !candidates.isLoading && !library.isLoading && !library.isError && waiting.length === 0 && rows.length === 0;

  return (
    <Module label="Procedures" onChatAbout={onChatAbout} chatAboutLabel="what I have learned to do">
      {waiting.length > 0 && (
        <div role="group" aria-label="Waiting for your review">
          <h3 className="lbl">Waiting for your review</h3>
          <ul className="belief-list">
            {waiting.map((c) => (
              <li key={c.id} className="row">
                <span className="t">{c.name}</span>
                <span className="s">
                  <Chip kind="dotted">{status(c.status)}</Chip> from {c.source_kind.replace(/_/g, " ")} · {c.evidence_refs.length}{" "}
                  {c.evidence_refs.length === 1 ? "piece" : "pieces"} of evidence
                </span>
                <span className="belief-actions">
                  <ReviewProcedureCandidate candidate={c} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {library.isLoading && <p role="status" className="note">Reading my playbooks…</p>}
      {library.isError && (
        <p className="note">
          Could not load procedures. <Control onClick={() => void library.refetch()}>Retry</Control>
        </p>
      )}
      {nothing && <p className="note">No procedures yet. Admitted playbooks will show here.</p>}

      {rows.length > 0 && (
        <div role="group" aria-label="What I know how to do">
          <h3 className="lbl">What I know how to do</h3>
          <ul className="belief-list">
            {rows.map((row) => (
              <li key={row.id} className="row">
                <button type="button" className="ctl-text entity-hit" onClick={() => setSelectedId(row.id)}>
                  <span className="t">{row.name}</span>
                  <span className="s">
                    {status(row.identity_status)} · version {row.version_number} · {row.trigger}
                  </span>
                </button>
                {onChatAboutProcedure && (
                  <span className="belief-actions">
                    <Control
                      aria-label={`Chat about ${row.name}`}
                      onClick={() => onChatAboutProcedure({ id: row.id, name: row.name }, document.body)}
                    >
                      Chat about this
                    </Control>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {selected && (
        <div className="procedure-detail">
          <h3 className="lbl">{selected.name}</h3>
          <ProcedureControls detail={selected} />
          <h4 className="lbl">Evidence</h4>
          <ul className="belief-list">
            {selected.versions.flatMap((v) =>
              v.evidence_refs.map((ref) => (
                <li key={`${v.id}-${ref.id}`} className="note">
                  {ref.kind} · {ref.id} · version {v.version_number}
                </li>
              )),
            )}
          </ul>
          <h4 className="lbl">Outcomes</h4>
          <ul className="belief-list">
            {selected.outcomes.map((o) => (
              <li key={`${o.procedure_version_id}-${o.summary}`} className="note">
                {o.outcome}: {o.summary}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Module>
  );
}
