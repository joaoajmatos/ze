import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { RoutingBadge, ScreenTraceLine } from "@/entities/message-trace";
import { TraceSection } from "@/entities/message-trace";

interface RoutingSectionProps {
  trace: WsTraceUpdateFrame;
  live?: boolean;
}

export function RoutingSection({ trace, live }: RoutingSectionProps) {
  return (
    <TraceSection title="Routing" loading={live && !trace.agent}>
      <RoutingBadge
        agent={trace.agent}
        routingMethod={trace.routing_method}
        confidence={trace.confidence}
        scoreGap={trace.score_gap}
        isCompound={trace.is_compound}
        subtasks={trace.subtasks}
        totalDurationMs={trace.total_duration_ms}
        tier={trace.tier}
      />
      <ScreenTraceLine screen={trace.screen} />
    </TraceSection>
  );
}
