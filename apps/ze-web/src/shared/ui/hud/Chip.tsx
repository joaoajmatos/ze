import type { ReactNode } from "react";

/** A claim-posture tag: solid is told, dotted is inferred or suspected. */
export function Chip({ kind = "solid", children }: { kind?: "solid" | "dotted"; children: ReactNode }) {
  return <span className={`chip ${kind}`}>{children}</span>;
}
