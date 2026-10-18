import type { WriteConfirmationOutcomeResponse } from "@myguyze/ze-client";
import { groupByRound, outcomeLabel } from "./format";
import { TraceRow } from "./TraceRow";

export function ConfirmationsRow({ outcomes }: { outcomes: WriteConfirmationOutcomeResponse[] | undefined }) {
  if (!outcomes || outcomes.length === 0) return null;
  return (
    <TraceRow title="Confirmations" count={outcomes.length}>
      {groupByRound(outcomes).map(([round, items]) => (
        <div key={round} role="group" aria-label={`Round ${round}`}>
          <p className="lbl">Round {round}</p>
          <ul className="tr-list">
            {items.map((o) => (
              <li key={`${o.request_id}-${o.item_id}`}>
                <span className="key">{o.tool ?? o.agent}</span>
                <span className="chip">{outcomeLabel(o.outcome)}</span>
                {o.summary && <span className="muted">{o.summary}</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </TraceRow>
  );
}
