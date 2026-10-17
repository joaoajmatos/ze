import { useCostAnomaliesQuery, useCostsQuery, formatAgentName } from "@/entities/cost-entry";
import { Module, SeriesSpark } from "@/shared/ui/hud";
import { dailyAverages, padDays } from "../lib/days";
import { formatCost, formatTotal } from "../lib/money";

const TOP_FLOWS = 5;

function ago(iso: string): string {
  const hours = Math.floor((Date.now() - new Date(iso).getTime()) / 3_600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Governance › Spend: is the last week's spend normal against the last 30 days? */
export function Spend() {
  const costs = useCostsQuery();
  const anomalies = useCostAnomaliesQuery();
  const label = "Am I spending normally?";

  if (costs.isError || !costs.data) {
    return (
      <Module label={label}>
        {costs.isError ? (
          <p className="gov-err">
            Could not load spend.{" "}
            <button type="button" className="ctl-text" onClick={() => void costs.refetch()}>
              Retry
            </button>
          </p>
        ) : (
          <p className="gov-note">Loading spend…</p>
        )}
      </Module>
    );
  }

  const days = padDays(costs.data.by_day);
  const { last7, last30 } = dailyAverages(days);
  const flows = Object.entries(costs.data.by_agent)
    .map(([key, b]) => ({ name: formatAgentName(key), usd: b.usd }))
    .sort((a, b) => b.usd - a.usd);
  const top = flows.slice(0, TOP_FLOWS);
  const rest = flows.slice(TOP_FLOWS).reduce((sum, f) => sum + f.usd, 0);
  if (flows.length > TOP_FLOWS) top.push({ name: "Others", usd: rest });
  const items = anomalies.data?.anomalies ?? [];

  return (
    <Module label={label}>
      <div className="gov-stack">
        <div className="gov-figure">
          <p className="sentence">
            Last 7 days <span className="key">{formatTotal(last7)}/day</span> vs 30-day{" "}
            <span className="key">{formatTotal(last30)}/day</span>
          </p>
        </div>
        <div className="gov-figure">
          <span data-testid="anomaly-count" className={`num md${items.length > 0 ? " hot" : ""}`}>
            {items.length}
          </span>
          <span className="muted">{items.length === 1 ? "unusual run" : "unusual runs"} in 30 days</span>
          <span className="ro">{formatTotal(costs.data.total_usd)} total</span>
        </div>
        <SeriesSpark values={days.map((d) => d.usd)} label="Spend per day, last 30 days" format={formatTotal} width={320} height={28} />
        <ul className="gov-list" aria-label="Spend by flow, last 30 days" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {top.map((f) => (
            <li key={f.name} className="row gov-row">
              <span className="t">{f.name}</span>
              <span className="ro">{formatTotal(f.usd)}</span>
            </li>
          ))}
        </ul>
        {items.length > 0 && (
          <ul aria-label="Unusual runs" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {items.map((a) => (
              <li key={`${a.agent}-${a.detected_at}`} className="row hot gov-row">
                <span className="t">
                  {formatAgentName(a.agent)} <span className="ro hot">{a.multiplier.toFixed(1)}×</span>
                </span>
                <span className="ro">{ago(a.detected_at)}</span>
                <span className="s">
                  <span className="ro">
                    {formatCost(a.run_cost_usd)} vs {formatCost(a.baseline_cost_usd)}
                  </span>{" "}
                  baseline
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Module>
  );
}
