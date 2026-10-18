import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { toolLanes } from "../../lib/instruments/tools";

/** Tool calls in order and duration, one lane per owning agent. Lanes share no clock. */
export function ToolsTimeline({ trace, partial = false, highlight = [] }: { trace: Partial<WsTraceUpdateFrame>; partial?: boolean; highlight?: string[] }) {
  const lanes = toolLanes(trace.tool_calls, trace.agent ?? "", partial);
  if (lanes.length === 0) return <p className="muted">No tools used.</p>;
  return (
    <div className="tr-tools">
      {lanes.map((lane) => {
        const end = Math.max(lane.span, 1);
        return (
          <div key={lane.agent} className="tr-lane" role="group" aria-label={`${lane.agent} tools`}>
            <span className="lbl">{lane.agent}</span>
            <div className="tr-track">
              {lane.calls.map((c, i) => (
                <i
                  key={i}
                  className={`tr-call${c.failed ? " failed" : ""}${highlight.includes(c.name) ? " hl" : ""}`}
                  style={partial ? { left: `${(i / Math.max(lane.calls.length, 1)) * 100}%` } : { left: `${(c.x / end) * 100}%`, width: `${Math.max((c.w / end) * 100, 2)}%` }}
                  title={c.name}
                />
              ))}
            </div>
            <ul>
              {lane.calls.map((c, i) => (
                <li key={i} data-highlight={highlight.includes(c.name) ? "" : undefined}>
                  <span className="key">{c.name}</span>
                  <span className="ro muted">{c.returned ? "returned" : `${c.durationMs} ms`}</span>
                  {c.irreversible && <span className="lbl tr-flag">irreversible</span>}
                  {c.gateWords && <span className="lbl tr-flag tr-gate">{c.gateWords}</span>}
                  {c.failed && <span className="lbl tr-flag">failed</span>}
                  {c.note && <span className="ro muted">{c.note}</span>}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <p className="ro muted">order and duration per lane; start times not recorded</p>
    </div>
  );
}
