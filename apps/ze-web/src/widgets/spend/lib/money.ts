/** Totals and averages: two decimals. */
export function formatTotal(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

/** A run or baseline cost: four decimals under $1, where two would hide it. */
export function formatCost(usd: number): string {
  return usd < 1 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}
