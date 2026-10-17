import type { DailyCostBucket } from "@myguyze/ze-client";

const DAY_MS = 86_400_000;

/** The API sends only days with spend; pad to `count` UTC calendar days ending today (UTC). */
export function padDays(byDay: readonly DailyCostBucket[], now: Date = new Date(), count = 30): DailyCostBucket[] {
  const known = new Map(byDay.map((d) => [d.date, d]));
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const out: DailyCostBucket[] = [];
  for (let i = count - 1; i >= 0; i--) {
    const date = new Date(today - i * DAY_MS).toISOString().slice(0, 10);
    out.push(known.get(date) ?? { date, usd: 0, calls: 0 });
  }
  return out;
}

/**
 * Daily averages over the last 7 days and the 30-day window; absent days count as zero.
 * An install younger than the window divides by the days since its first bucket, so a new
 * install does not read as a spike. Today's partial day counts as a whole day.
 */
export function dailyAverages(padded: readonly DailyCostBucket[], firstDate?: string): { last7: number; last30: number } {
  const sum = (days: readonly DailyCostBucket[]) => days.reduce((a, d) => a + d.usd, 0);
  const today = padded[padded.length - 1]?.date;
  const age = firstDate && today ? Math.round((Date.parse(today) - Date.parse(firstDate)) / DAY_MS) + 1 : padded.length;
  const window = Math.max(1, Math.min(padded.length, age));
  const week = Math.min(7, window);
  return { last7: sum(padded.slice(-week)) / week, last30: sum(padded.slice(-window)) / window };
}
