import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { TraceRow } from "./TraceRow";

function hasConductor(trace: WsTraceUpdateFrame): boolean {
  const hint = trace.conductor_hint;
  const ledger = trace.conductor_ledger ?? [];
  return Boolean((hint && hint.length > 0) || ledger.length > 0);
}

export function ConductorRow({ trace, live }: { trace: WsTraceUpdateFrame; live?: boolean }) {
  if (!hasConductor(trace)) return null;
  const hint = trace.conductor_hint ?? [];
  const ledger = trace.conductor_ledger ?? [];
  return (
    <TraceRow title="Conductor" loading={live && ledger.length === 0 && hint.length === 0}>
      {hint.length > 0 && (
        <ul className="tr-list" aria-label="Hint">
          {hint.map((item, i) => (
            <li key={`${item.agent}-${i}`}>
              <span className="key">{item.agent}</span>
              {item.prompt ? <span className="muted"> — {item.prompt}</span> : null}
            </li>
          ))}
        </ul>
      )}
      {ledger.length > 0 && (
        <ul className="tr-list">
          {ledger.map((entry, i) => (
            <li key={`${entry.agent}-${entry.status}-${i}`}>
              <span className="key">{entry.agent}</span>
              <span className="chip">{entry.status}</span>
              {entry.request_id ? <span className="ro muted">{entry.request_id}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </TraceRow>
  );
}
