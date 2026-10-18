import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { useState } from "react";
import { toolLanes } from "../../lib/instruments/tools";
import { groupScriptRows, isDelegateLike, scriptSummary, type ScriptNode } from "../../lib/script-rows";

function ScriptRow({ node }: { node: ScriptNode }) {
  const [open, setOpen] = useState(false);
  const script = node.call.script;
  return (
    <div className="tr-script">
      <button type="button" className="tr-script-toggle ro" aria-expanded={open} onClick={() => setOpen(!open)}>
        {scriptSummary(node)}
      </button>
      {open && (
        <>
          {script && <pre className="tr-script-src">{script.source}</pre>}
          {script?.source_cut && <p className="ro muted">Source cut to fit the trace.</p>}
          <ul>
            {node.children.map((c, i) => (
              <li key={c.call_id ?? i}>
                <span className="key">{c.name}</span>
                <span className="ro muted">{c.duration_ms} ms</span>
                {c.success === false && <span className="lbl tr-flag">failed</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** Tool calls in order and duration, one lane per owning agent. Placed by start time where recorded. */
export function ToolsTimeline({ trace, partial = false, highlight = [] }: { trace: Partial<WsTraceUpdateFrame>; partial?: boolean; highlight?: string[] }) {
  const nodes = groupScriptRows(trace.tool_calls ?? []);
  const scripts = new Map(nodes.filter((n) => isDelegateLike(n.call.access) && n.call.script).map((n) => [n.call.call_id, n]));
  const lanes = toolLanes(nodes.map((n) => n.call), trace.agent ?? "", partial);
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
                  key={c.id}
                  className={`tr-call${c.failed ? " failed" : ""}${highlight.includes(c.name) ? " hl" : ""}`}
                  style={c.returned ? { left: `${(i / Math.max(lane.calls.length, 1)) * 100}%` } : { left: `${(c.x / end) * 100}%`, width: `${Math.max((c.w / end) * 100, 2)}%` }}
                  title={c.name}
                />
              ))}
            </div>
            <ul>
              {lane.calls.map((c) => (
                <li key={c.id} data-highlight={highlight.includes(c.name) ? "" : undefined}>
                  <span className="key">{c.name}</span>
                  {scripts.has(c.id) && <ScriptRow node={scripts.get(c.id)!} />}
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
      <p className="ro muted">{lanes.every((l) => l.timed) ? "placed by start time" : "order and duration per lane; start times not recorded"}</p>
    </div>
  );
}
