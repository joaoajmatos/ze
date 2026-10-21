import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { coordinateOf, routingFor } from "../../lib/instruments/routing";

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** How the specialist was chosen: the bar says what produced it, the needles show the options, the line names the tier. */
export function RoutingInstrument({ trace, settled = true }: { trace: Partial<WsTraceUpdateFrame>; settled?: boolean }) {
  const r = routingFor(trace, settled);
  const coordinate = coordinateOf(trace);
  return (
    <div className="tr-routing">
      <p className="ro">
        {trace.agent} · {r.methodWords}
      </p>
      {r.bar && (
        <div className="tr-bar-wrap">
          <span className="lbl">{r.bar.label}</span>
          {r.bar.value !== null && (
            <div className="tr-bar" role="meter" aria-label={r.bar.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(r.bar.value * 100)}>
              {r.bar.ghost !== null && <i className="tr-ghost" style={{ width: pct(r.bar.ghost) }} />}
              <i className="tr-fill" style={{ width: pct(r.bar.value) }} />
            </div>
          )}
          {r.bar.value !== null && (
            <p className="ro">
              {pct(r.bar.value)}
              {r.bar.ghost !== null && <span className="muted"> · runner-up {pct(r.bar.ghost)}</span>}
            </p>
          )}
        </div>
      )}
      {r.scores.length > 0 && (
        <ul className="tr-shortlist" aria-label="Shortlist scores">
          {r.scores.map((sc) => (
            <li key={sc.agent} data-chosen={sc.chosen ? "" : undefined}>
              <span className="ro">{sc.agent}</span>
              <div className="tr-bar" role="meter" aria-label={`${sc.agent} score`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(sc.score * 100)}>
                <i className="tr-fill" style={{ width: pct(sc.score) }} />
                {r.thresholds && <i className="tr-threshold" style={{ left: pct(r.thresholds.threshold) }} aria-hidden="true" />}
              </div>
              <span className="ro">{pct(sc.score)}</span>
            </li>
          ))}
          {r.thresholds && <li className="ro muted">{`threshold ${pct(r.thresholds.threshold)} · gap ${pct(r.thresholds.gap)}`}</li>}
        </ul>
      )}
      {r.options.length > 0 && (
        <ul className="tr-needles" aria-label="Options considered">
          {r.options.map((o) => (
            <li key={o.name} data-chosen={o.chosen ? "" : undefined}>
              <span className="ro">{o.name}</span>
              <span className="tr-needle" style={{ left: pct(o.probability) }} aria-hidden="true" />
              <span className="ro">{pct(o.probability)}</span>
            </li>
          ))}
        </ul>
      )}
      {r.tierLine && <p className="ro">{r.tierLine}</p>}
      {coordinate && <p className="lbl" data-testid="coordinate">{coordinate}</p>}
    </div>
  );
}
