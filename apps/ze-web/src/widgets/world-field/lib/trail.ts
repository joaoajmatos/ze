export interface Trail {
  from: number;
  to: number;
}

/** The dotted trail runs from where confidence stood to where it is now; with no recorded prior there is none. */
export function trailOf(prior: number | null, current: number | null): Trail | null {
  if (prior == null || current == null) return null;
  if (Math.abs(prior - current) < 0.02) return null;
  return { from: prior, to: current };
}
