import type { WriteConfirmationOutcomeResponse } from "@myguyze/ze-client";
import { TraceSection } from "@/entities/message-trace";
import { groupByRound, outcomeLabel } from "./lib/format";

interface ConfirmationsSectionProps {
  outcomes: WriteConfirmationOutcomeResponse[] | undefined;
}

export function ConfirmationsSection({ outcomes }: ConfirmationsSectionProps) {
  if (!outcomes || outcomes.length === 0) return null;

  return (
    <TraceSection title="Confirmations" count={outcomes.length}>
      <div className="space-y-2">
        {groupByRound(outcomes).map(([round, items]) => (
          <div key={round} role="group" aria-label={`Round ${round}`}>
            <p className="text-[10px] uppercase tracking-wide text-smoke/80 mb-1">Round {round}</p>
            <ul className="space-y-1.5">
              {items.map((o) => (
                <li key={`${o.request_id}-${o.item_id}`} className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="font-mono text-foreground/90">{o.tool ?? o.agent}</span>
                  <span className="px-1.5 py-0.5 rounded bg-foreground/[0.06] text-smoke text-[10px]">
                    {outcomeLabel(o.outcome)}
                  </span>
                  {o.summary && <span className="basis-full text-smoke">{o.summary}</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </TraceSection>
  );
}
