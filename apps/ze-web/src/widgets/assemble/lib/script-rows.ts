import type { WsTraceUpdateFrame } from "@myguyze/ze-client";

type Call = WsTraceUpdateFrame["tool_calls"][number];

export interface ScriptNode {
  call: Call;
  /** The calls the script made, in order; empty for any other row. */
  children: Call[];
}

/** A row that stands for calls made inside it: a delegate's or a script's. */
export function isDelegateLike(access: string | undefined): boolean {
  return access === "delegate" || access === "script";
}

/** Nests each row under the script row its `parent_call_id` names; an orphan stays top level. */
export function groupScriptRows(calls: Call[]): ScriptNode[] {
  const scriptIds = new Set(calls.filter((c) => c.script && c.call_id).map((c) => c.call_id));
  const children = new Map<string, Call[]>();
  const top: Call[] = [];
  for (const c of calls) {
    if (c.parent_call_id && scriptIds.has(c.parent_call_id)) children.set(c.parent_call_id, [...(children.get(c.parent_call_id) ?? []), c]);
    else top.push(c);
  }
  return top.map((call) => ({ call, children: (call.call_id && children.get(call.call_id)) || [] }));
}

export function scriptSummary(node: ScriptNode): string {
  const s = node.call.script;
  const outcome = s?.limit ? `limit: ${s.limit}` : (s?.outcome ?? "ok");
  const n = node.children.length;
  return `Script · ${outcome} · ${n} ${n === 1 ? "call" : "calls"} · ${node.call.duration_ms} ms`;
}
