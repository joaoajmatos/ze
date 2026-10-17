const DAY = 86400_000;

export function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

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

export function ago(d: Date | null, now: Date): string {
  if (!d) return "—";
  const m = Math.round((now.getTime() - d.getTime()) / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

export function hhmm(d: Date): string {
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

export function weekday(d: Date): string {
  return d.toLocaleDateString("en-GB", { weekday: "short" });
}

export function dayMonth(d: Date): string {
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function longDate(d: Date): string {
  return d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export function pct(c: number | null): string {
  return c == null ? "—" : `${Math.round(c * 100)}%`;
}


/** 0 when fresh, 1 when the claim has gone 30 days without new evidence. */
export function staleness(updated: Date | null, now: Date): number {
  if (!updated) return 0;
  return Math.min(1, Math.max(0, (now.getTime() - updated.getTime()) / (30 * DAY)));
}

const SOURCE_LABEL: Record<string, string> = {
  user_declared: "you said",
  conversation: "chat",
  email: "email",
  calendar: "calendar",
  ingestion: "a document",
  correlation: "Ze inferred",
  companion: "chat",
};

export function sourceLabel(s: string | null): string {
  if (!s) return "—";
  return SOURCE_LABEL[s] ?? s.replace(/_/g, " ");
}

const STATE_LABEL: Record<string, string> = {
  suspected: "Suspected",
  active: "Active",
  drifting: "Drifting",
  closed: "Closed",
  dropped: "Dropped",
  awaiting_gate: "Waiting on you",
  planning: "Planning",
  hypothesis: "Inference",
  relationship: "Relationship",
};

export function stateLabel(s: string): string {
  return STATE_LABEL[s] ?? s.replace(/_/g, " ");
}

