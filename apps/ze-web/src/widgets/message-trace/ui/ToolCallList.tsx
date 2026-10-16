import type { ToolCallTraceResponse } from "@myguyze/ze-client";
import { CheckCircle, XCircle } from "lucide-react";
import { gateLabel } from "../lib/format";

interface ToolCallListProps {
  toolCalls: ToolCallTraceResponse[];
}

export function ToolCallList({ toolCalls }: ToolCallListProps) {
  if (toolCalls.length === 0) {
    return <p className="text-xs text-smoke/80 italic">No tools called</p>;
  }

  return (
    <ul className="space-y-1.5">
      {toolCalls.map((tc, i) => (
        <li key={i} className="flex items-center gap-2 text-xs">
          {tc.success ? (
            <CheckCircle className="w-3 h-3 text-success flex-shrink-0" />
          ) : (
            <XCircle className="w-3 h-3 text-destructive flex-shrink-0" />
          )}
          <span className="font-mono text-foreground/90">{tc.name}</span>
          {gateLabel(tc.gate) && (
            <span
              data-testid="tool-gate"
              className="rounded-pill border border-foreground/10 px-1.5 text-[10px] text-smoke"
            >
              {gateLabel(tc.gate)}
            </span>
          )}
          <span className="text-smoke">{tc.duration_ms}ms</span>
          {tc.result_snippet && (
            <span className="text-smoke/80 truncate max-w-[160px]">{tc.result_snippet}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
