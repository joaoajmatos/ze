import type { RollbackRecordResponse, RollbackTraceResponse } from "@myguyze/ze-client";
import { useSession } from "@/entities/session";
import { TraceSection } from "@/entities/message-trace";

interface RollbackSectionProps {
  /** On a regenerated reply: what was undone before it was written. */
  rollback?: RollbackTraceResponse | null;
  /** On a retried reply: the stored rollback record. */
  record?: RollbackRecordResponse | null;
  live?: boolean;
}

const OUTCOME_LABEL = {
  undone: "Undone",
  failed: "Could not undo",
  not_attempted: "Not attempted",
} as const;

function Entries({ entries }: { entries: RollbackTraceResponse["entries"] }) {
  return (
    <ul className="space-y-1">
      {(entries ?? []).map((entry) => (
        <li key={entry.entry_id} className="flex gap-2">
          <span className="text-foreground/90">{entry.effect_phrase}</span>
          <span className="text-smoke/80">{OUTCOME_LABEL[entry.outcome]}</span>
        </li>
      ))}
    </ul>
  );
}

export function RollbackSection({ rollback, record, live }: RollbackSectionProps) {
  const setHighlightMessage = useSession((s) => s.setHighlightMessage);
  if (live || (!rollback && !record)) return null;

  return (
    <TraceSection title="Rollback" count={(rollback ?? record)?.entries?.length ?? 0}>
      <div className="space-y-1.5 text-xs">
        {rollback && (
          <>
            <p className="text-foreground/90">Rolled back before this reply</p>
            <Entries entries={rollback.entries} />
            <button
              type="button"
              onClick={() => setHighlightMessage(rollback.replaces)}
              className="text-plum-voltage underline underline-offset-2"
            >
              View replaced reply
            </button>
          </>
        )}
        {!rollback && record && (
          <>
            <p className="text-foreground/90">Rollback during retry</p>
            <Entries entries={record.entries} />
          </>
        )}
      </div>
    </TraceSection>
  );
}
