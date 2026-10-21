import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { describeJudgments } from "../../lib/instruments/judgments";

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** What System One was asked, grouped by where the answer was used, with the decision line for what Ze kept. */
export function JudgmentGauges({ trace }: { trace: Partial<WsTraceUpdateFrame> }) {
  const { groups, outcome } = describeJudgments(trace.judgments);
  if (groups.length === 0 && !outcome) return <p className="muted">No judgments on this reply.</p>;
  return (
    <div className="tr-judgments">
      {groups.map((g) => (
        <div key={g.surface} role="group" aria-label={g.label}>
          <p className="lbl">{g.label}</p>
          <ul>
            {g.rows.map((row) => (
              <li key={row.id} data-status={row.status}>
                <span className="key">{row.label}</span>
                {row.shape === "choice" && <span className="ro on">{row.answer ?? "no answer"}</span>}
                {row.value !== null && <span className="ro on">{pct(row.value)}</span>}
                {row.options.length > 0 && (
                  <span className="ro muted">
                    {row.options.map((o) => `${o.name} ${pct(o.probability)}`).join(" · ")}
                  </span>
                )}
                {row.bar && <span className="ro muted">{`bar ${row.bar.name} ${pct(row.bar.value)}`}</span>}
                {row.uncalibrated && <span className="ro muted">uncalibrated</span>}
                {row.status === "skipped" ? <span className="ro muted">skipped: {row.reason}</span> : <span className="ro muted">used</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {outcome && (
        <p className="tr-decision" data-testid="intake-decision">
          <span className="lbl">Decision</span> <span className="ro on">{outcome.words}</span>
        </p>
      )}
    </div>
  );
}
