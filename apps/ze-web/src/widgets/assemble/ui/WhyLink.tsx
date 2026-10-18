import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { whyFor, type WhyTarget } from "../lib/why";

/** "Why?" on a reply. Hidden when the reply has no trace. */
export function WhyLink({ trace, onOpen }: { trace: WsTraceUpdateFrame | undefined; onOpen: (target: WhyTarget) => void }) {
  const target = whyFor(trace);
  if (!target) return null;
  return (
    <button type="button" className="ctl-text assemble-why" onClick={() => onOpen(target)}>
      <span className="lbl on">Why?</span>
    </button>
  );
}
