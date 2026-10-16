const GATE_LABEL: Record<string, string> = {
  approved: "Approved",
  pre_approved: "Pre-approved",
  denied: "Denied",
  refused: "Refused",
  refused_over_cap: "Refused",
  expired: "Timed out",
  duplicate: "Not repeated",
  held: "Held",
};

/** Short label for a tool call's confirmation gate, or null when it ran ungated. */
export function gateLabel(gate: string | undefined): string | null {
  return gate ? (GATE_LABEL[gate] ?? null) : null;
}
