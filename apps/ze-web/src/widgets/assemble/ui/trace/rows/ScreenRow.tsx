import type { ScreenTraceResponse } from "@myguyze/ze-client";
import { TraceRow } from "./TraceRow";

const STATUS_WORDS: Record<string, string> = {
  ok: "read",
  missing: "not found",
  changed: "changed since you saw it",
  failed: "failed",
  timeout: "timed out",
  cut: "cut for length",
};

/** What Ze looked up about the screen the question came from, and how each lookup went. */
export function ScreenRow({ screen }: { screen: ScreenTraceResponse | null | undefined }) {
  const resolvers = screen?.resolvers ?? [];
  if (resolvers.length === 0) return null;
  return (
    <TraceRow title="Screen lookups" count={resolvers.length}>
      <ul className="tr-list">
        {resolvers.map((r, i) => (
          <li key={`${r.kind}-${r.id}-${i}`} data-status={r.status}>
            <span className="key">{r.kind}</span>
            <span className="chip">{STATUS_WORDS[r.status] ?? r.status}</span>
            {r.ms != null && <span className="ro muted">{r.ms} ms</span>}
          </li>
        ))}
      </ul>
    </TraceRow>
  );
}
