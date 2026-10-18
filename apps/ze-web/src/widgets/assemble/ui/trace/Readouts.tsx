import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { DotMatrix } from "@/shared/ui";
import { readoutsFor } from "../../lib/instruments/readouts";

const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;
const pct = (v: number) => `${Math.round(v * 100)}%`;
const money = (usd: number) => `$${usd.toFixed(4)}`;
const count = (n: number) => n.toLocaleString("en-US");

export function Readouts({ trace }: { trace: Partial<WsTraceUpdateFrame> }) {
  const r = readoutsFor(trace);
  const est = r.usage?.estimated ? " est." : "";
  return (
    <dl className="tr-readouts">
      {r.total ? (
        <div>
          <dt className="lbl">Total</dt>
          <dd>
            <DotMatrix text={`${(r.total.ms / 1000).toFixed(1)} S`} size={3} title={`${r.total.ms} milliseconds for the whole turn`} />
            {r.total.partial && <span className="ro muted"> partial</span>}
          </dd>
        </div>
      ) : (
        <div>
          <dt className="lbl">Tool time</dt>
          <dd>
            <DotMatrix text={`${(r.toolMs / 1000).toFixed(1)} S`} size={3} title={`${r.toolMs} milliseconds of tool time`} />
          </dd>
        </div>
      )}
      {r.total && r.activeMs !== null && (
        <>
          <div>
            <dt className="lbl">Active</dt>
            <dd className="ro">{seconds(r.activeMs)}</dd>
          </div>
          <div>
            <dt className="lbl">Tool time</dt>
            <dd className="ro">{seconds(r.toolMs)}</dd>
          </div>
        </>
      )}
      <div>
        <dt className="lbl">Model</dt>
        <dd className="ro">{r.model}</dd>
      </div>
      {r.usage && (
        <>
          <div>
            <dt className="lbl">Tokens</dt>
            <dd className="ro">
              {`${count(r.usage.promptTokens)} in · ${count(r.usage.completionTokens)} out`}
              {est && <span className="muted">{est}</span>}
            </dd>
          </div>
          <div>
            <dt className="lbl">Cost</dt>
            <dd className="ro">
              {money(r.usage.costUsd)}
              {est && <span className="muted">{est}</span>}
            </dd>
          </div>
          {r.usage.fill && (
            <div>
              <dt className="lbl">Context</dt>
              <dd>
                <div className="tr-bar" role="meter" aria-label="Context fill" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(r.usage.fill.bar * 100)}>
                  <i className="tr-fill" style={{ width: pct(r.usage.fill.bar) }} />
                </div>
                <span className="ro">{pct(r.usage.fill.value)}</span>
                {est && <span className="ro muted">{est}</span>}
              </dd>
            </div>
          )}
          {r.usage.systemOneTokens > 0 && (
            <div>
              <dt className="lbl">System One tokens</dt>
              <dd className="ro">{`${count(r.usage.systemOneTokens)} tokens`}</dd>
            </div>
          )}
        </>
      )}
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
