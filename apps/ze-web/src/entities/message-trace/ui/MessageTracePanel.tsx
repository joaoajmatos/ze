import { useMessageTraceQuery } from "../api/useMessageTraceQuery";
import { MemoryChunkList } from "./MemoryChunkList";
import { RoutingBadge } from "./RoutingBadge";
import { ScreenTraceLine } from "./ScreenTraceLine";
import { ToolCallList } from "./ToolCallList";
import { TraceSection } from "./TraceSection";

interface MessageTracePanelProps {
  messageId: string;
}

export function MessageTracePanel({ messageId }: MessageTracePanelProps) {
  const { data: trace, isLoading, isError } = useMessageTraceQuery(messageId, true);

  if (isLoading) {
    return (
      <div className="mt-1 rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-3 py-2 text-xs text-smoke">
        Loading trace…
      </div>
    );
  }

  if (isError) {
    return (
      <div role="alert" className="mt-1 rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-3 py-2 text-xs text-smoke/80 italic">
        Could not load the trace.
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="mt-1 rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-3 py-2 text-xs text-smoke/80 italic">
        No trace available for this message.
      </div>
    );
  }

  return (
    <div className="mt-1 rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] overflow-hidden text-xs">
      <TraceSection title="Routing">
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

      <TraceSection title="Memory retrieved" count={trace.memory_chunks.length}>
        <MemoryChunkList chunks={trace.memory_chunks} />
      </TraceSection>

      <TraceSection title="Tools called" count={trace.tool_calls.length}>
        <ToolCallList toolCalls={trace.tool_calls} />
      </TraceSection>
    </div>
  );
}
