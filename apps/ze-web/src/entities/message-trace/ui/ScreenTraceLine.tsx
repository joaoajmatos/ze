import type { ScreenTraceResponse } from "@myguyze/ze-client";
import { screenTraceLine } from "../lib/screen-line";

/** Where the person asked from, or what they asked about. Renders nothing without a screen trace. */
export function ScreenTraceLine({ screen }: { screen?: ScreenTraceResponse | null }) {
  const line = screenTraceLine(screen);
  if (!line) return null;
  return (
    <p className="mt-1 text-[11px] text-smoke" data-testid="screen-trace-line">
      {line}
    </p>
  );
}
