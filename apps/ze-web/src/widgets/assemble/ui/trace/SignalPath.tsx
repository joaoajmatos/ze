import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { useReducedMotion } from "@/shared/lib";
import { stagesFor } from "../../lib/instruments/signal";

interface SignalPathProps {
  trace: Partial<WsTraceUpdateFrame>;
  streaming: boolean;
}

const seconds = (ms: number) => `+${(ms / 1000).toFixed(1)} s`;

/** The turn as a hairline from the origin point: one tick per stage the server recorded, offsets from the turn start. */
export function SignalPath({ trace, streaming }: SignalPathProps) {
  const reduced = useReducedMotion();
  const path = stagesFor(trace, streaming);
  const newest = path.stages.length - 1;
  return (
    <div className="tr-signal" role="group" aria-label="Signal path">
      <ol className="tr-signal-strip">
        <li className="tr-origin" aria-hidden="true" />
        {path.stages.map((s, i) => (
          <li key={`${i}:${s.key}`} className="tr-tick" data-stage={s.key} data-live={streaming && i === newest ? "" : undefined} data-gap={s.gapMs !== null ? "" : undefined}>
            {s.gapMs !== null && <span className="ro muted">{`waited ${(s.gapMs / 1000).toFixed(1)} s`}</span>}
            <span className="lbl">{s.label}</span>
            <span className="ro">{s.offsetMs !== null ? seconds(s.offsetMs) : (s.detail ?? "")}</span>
            {s.offsetMs !== null && s.detail && <span className="ro muted">{s.detail}</span>}
          </li>
        ))}
        {path.replyPending && (
          <li className="tr-tick tr-pending" aria-label="reply coming">
            <span className="lbl">reply</span>
            <span className="ro">…</span>
          </li>
        )}
      </ol>
      {streaming && !reduced && <span className="tr-sweep" data-testid="signal-sweep" aria-hidden="true" />}
    </div>
  );
}
