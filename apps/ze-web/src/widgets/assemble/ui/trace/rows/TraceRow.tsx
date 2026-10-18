import type { ReactNode } from "react";

/** A titled block of readouts in the trace rail. */
export function TraceRow({ title, count, loading, children }: { title: string; count?: number; loading?: boolean; children: ReactNode }) {
  return (
    <section className="tr-row" aria-label={title}>
      <h3 className="lbl">
        {title}
        {count !== undefined && !loading && <span className="muted"> ({count})</span>}
      </h3>
      {children}
    </section>
  );
}
