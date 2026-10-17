const DAY = 86_400_000;

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

/** Calendar days from `b` to `a`. */
export function dayDiff(a: Date, b: Date): number {
  return Math.round((startOfDay(a).getTime() - startOfDay(b).getTime()) / DAY);
}

export function relDay(d: Date, now: Date): string {
  const n = dayDiff(d, now);
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  if (n === -1) return "yesterday";
  return n > 0 ? `in ${n} days` : `${-n} days ago`;
}

/** Short elapsed time: "now", "5m", "3h", "2d". */
export function ago(d: Date | null, now: Date): string {
  if (!d) return "—";
  const m = Math.round((now.getTime() - d.getTime()) / 60_000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

export function pct(c: number | null): string {
  return c == null ? "—" : `${Math.round(c * 100)}%`;
}

/** "just now", "5 m ago", "3 h ago", "2 d ago". */
export function agoPhrase(d: Date | null, now: Date): string {
  const short = ago(d, now);
  if (short === "—") return short;
  if (short === "now") return "just now";
  return `${short.slice(0, -1)} ${short.slice(-1)} ago`;
}
