import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { TraceSection } from "@/widgets/message-trace/ui/TraceSection";

function hasConductor(trace: WsTraceUpdateFrame): boolean {
  const hint = trace.conductor_hint;
  const ledger = trace.conductor_ledger ?? [];
  return Boolean((hint && hint.length > 0) || ledger.length > 0);
}

interface ConductorSectionProps {
  trace: WsTraceUpdateFrame;
  live?: boolean;
}

export function ConductorSection({ trace, live }: ConductorSectionProps) {
  if (!hasConductor(trace)) {
    return null;
  }
  const hint = trace.conductor_hint ?? [];
  const ledger = trace.conductor_ledger ?? [];
  return (
    <TraceSection title="Conductor" loading={live && ledger.length === 0 && hint.length === 0}>
      {hint.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] uppercase tracking-wide text-smoke/80 mb-1">Hint</p>
          <ul className="space-y-1">
            {hint.map((item, i) => (
              <li key={`${item.agent}-${i}`} className="text-xs text-foreground/90">
                <span className="font-mono">{item.agent}</span>
                {item.prompt ? (
                  <span className="text-smoke"> — {item.prompt}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      {ledger.length > 0 && (
        <ul className="space-y-1.5">
          {ledger.map((entry, i) => (
            <li
              key={`${entry.agent}-${entry.status}-${i}`}
              className="flex items-center gap-2 text-xs flex-wrap"
            >
              <span className="font-mono text-foreground/90">{entry.agent}</span>
              <span className="px-1.5 py-0.5 rounded bg-foreground/[0.06] text-smoke text-[10px]">
                {entry.status}
              </span>
              {entry.request_id ? (
                <span className="font-mono text-[10px] text-smoke/80">
                  {entry.request_id}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </TraceSection>
  );
}
