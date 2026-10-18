import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { DotMatrix } from "@/shared/ui";
import { readoutsFor } from "../../lib/instruments/readouts";

export function Readouts({ trace }: { trace: Partial<WsTraceUpdateFrame> }) {
  const r = readoutsFor(trace);
  return (
    <dl className="tr-readouts">
      <div>
        <dt className="lbl">Total</dt>
        <dd>
          <DotMatrix text={`${(r.totalMs / 1000).toFixed(1)} S`} size={3} title={`${r.totalMs} milliseconds in total`} />
        </dd>
      </div>
      <div>
        <dt className="lbl">Model</dt>
        <dd className="ro">{r.model}</dd>
      </div>
      {r.systemOneText && (
        <div>
          <dt className="lbl">System One</dt>
          <dd className="ro">{r.systemOneText}</dd>
        </div>
      )}
      {r.compaction && (
        <div>
          <dt className="lbl">Compaction</dt>
          <dd className="ro">{r.compaction}</dd>
        </div>
      )}
      {r.resumeRecap && (
        <div>
          <dt className="lbl">Recap</dt>
          <dd className="ro">resume recap applied</dd>
        </div>
      )}
    </dl>
  );
}
