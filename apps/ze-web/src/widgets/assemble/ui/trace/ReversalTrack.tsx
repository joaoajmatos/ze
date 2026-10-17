import type { RollbackRecordResponse } from "@myguyze/ze-client";

const OUTCOME_WORDS: Record<string, string> = { undone: "undone", failed: "could not be undone", not_attempted: "not attempted" };
const STATE_WORDS: Record<string, string> = {
  partial: "Some actions could not be undone.",
  rolled_back_awaiting_confirmation: "Undone; waiting for your confirmation.",
  rolled_back_retry_failed: "Undone; the new reply failed.",
  superseded: "Replaced by a retry.",
};

/** What a retry undid, last action first. */
export function ReversalTrack({ rollback }: { rollback: RollbackRecordResponse | null | undefined }) {
  const entries = [...(rollback?.entries ?? [])].reverse();
  if (!rollback) return <p className="muted">Nothing was undone.</p>;
  return (
    <div className="tr-reversal">
      <p className="ro">{STATE_WORDS[rollback.state] ?? rollback.state}</p>
      <ol aria-label="Undone, last action first">
        {entries.map((e) => (
          <li key={e.entry_id} data-outcome={e.outcome}>
            <span className="key">{e.effect_phrase}</span>
            <span className="ro muted">{OUTCOME_WORDS[e.outcome] ?? e.outcome}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
