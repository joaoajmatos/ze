import type { TierTraceResponse } from "@myguyze/ze-client";

interface RoutingBadgeProps {
  agent: string;
  routingMethod: string;
  confidence: number;
  scoreGap: number;
  isCompound: boolean;
  subtasks: string[];
  totalDurationMs: number;
  tier?: TierTraceResponse | null;
}

function tierText(tier: TierTraceResponse): string | null {
  if (tier.decided_by === "no_simple_model") return null;
  if (tier.tier === "simple") {
    return tier.decided_by === "system_one" ? "Light model · System One" : null;
  }
  switch (tier.decided_by) {
    case "system_one":
      return "Full model · System One";
    case "off":
      return "Full model · tiering off";
    case "uncalibrated":
      return "Full model · tiering not calibrated";
    case "skip":
    case "invalid_answer":
      return "Full model · System One unavailable";
    case "compound":
      return "Full model · multi-agent turn";
    default:
      return null;
  }
}

export function RoutingBadge({
  agent,
  routingMethod,
  confidence,
  scoreGap,
  isCompound,
  subtasks,
  totalDurationMs,
  tier,
}: RoutingBadgeProps) {
  const confidencePct = Math.round(confidence * 100);
  const tierLine = tier ? tierText(tier) : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="px-1.5 py-0.5 rounded bg-plum-voltage/20 text-plum-voltage text-xs font-medium">
          {agent}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-foreground/[0.06] text-smoke text-xs">
          {routingMethod}
        </span>
        <span className="text-xs text-foreground font-medium">{confidencePct}% conf</span>
      </div>

      <div className="w-full bg-foreground/[0.06] rounded-full h-1">
        <div
          className="bg-plum-voltage h-1 rounded-full transition-all"
          style={{ width: `${confidencePct}%` }}
        />
      </div>

      <div className="flex gap-3 text-xs text-smoke">
        <span>Gap: {scoreGap.toFixed(2)}</span>
        <span>{isCompound ? `Compound (${subtasks.length})` : "Direct"}</span>
        {totalDurationMs > 0 && <span>{totalDurationMs}ms</span>}
      </div>

      {tierLine && <div className="text-xs text-smoke">{tierLine}</div>}

      {isCompound && subtasks.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {subtasks.map((s) => (
            <span
              key={s}
              className="px-1.5 py-0.5 rounded bg-foreground/[0.04] text-smoke text-[10px]"
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
