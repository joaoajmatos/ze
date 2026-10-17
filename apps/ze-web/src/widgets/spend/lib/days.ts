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

/** Daily averages over the last 7 and all padded days; absent days count as zero. */
export function dailyAverages(padded: readonly DailyCostBucket[]): { last7: number; last30: number } {
  const sum = (days: readonly DailyCostBucket[]) => days.reduce((a, d) => a + d.usd, 0);
  return { last7: sum(padded.slice(-7)) / 7, last30: sum(padded) / padded.length };
}
