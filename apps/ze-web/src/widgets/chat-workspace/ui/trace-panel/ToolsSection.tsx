import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { ToolCallList } from "@/entities/message-trace";
import { TraceSection } from "@/entities/message-trace";

interface ToolsSectionProps {
  toolCalls: WsTraceUpdateFrame["tool_calls"];
  live?: boolean;
}

export function ToolsSection({ toolCalls, live }: ToolsSectionProps) {
  return (
    <TraceSection title="Tools" count={toolCalls.length} loading={live && toolCalls.length === 0}>
      <ToolCallList toolCalls={toolCalls} />
    </TraceSection>
  );
}
