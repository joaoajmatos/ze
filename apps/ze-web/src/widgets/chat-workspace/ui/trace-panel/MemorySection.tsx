import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { MemoryChunkList } from "@/entities/message-trace";
import { TraceSection } from "@/entities/message-trace";

interface MemorySectionProps {
  chunks: WsTraceUpdateFrame["memory_chunks"];
  live?: boolean;
}

export function MemorySection({ chunks, live }: MemorySectionProps) {
  return (
    <TraceSection title="Memory" count={chunks.length} loading={live && chunks.length === 0}>
      <MemoryChunkList chunks={chunks} />
    </TraceSection>
  );
}
