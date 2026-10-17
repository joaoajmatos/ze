import type { WsTraceUpdateFrame } from "@myguyze/ze-client";

export type WhySection = "routing" | "tools";

export interface WhyTarget {
  section: WhySection;
  /** Tool names whose rows are highlighted: the ones that drew the reply's modules. */
  highlight: string[];
}

/**
 * Where "Why?" opens. Message components carry no call index, so the link points at the section the trace can
 * prove: Routing for a preset reply (it never ran a model), else Tools with the render and show rows marked.
 */
export function whyFor(trace: WsTraceUpdateFrame | undefined): WhyTarget | null {
  if (!trace) return null;
  if (trace.routing_method === "preset") return { section: "routing", highlight: [] };
  const highlight = (trace.tool_calls ?? []).map((c) => c.name).filter((name) => /^(render_|show_)/.test(name));
  return { section: "tools", highlight };
}
