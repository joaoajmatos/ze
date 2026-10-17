import { concernStateWords, dayDiff, pct, relDay } from "@/shared/lib";
import { shortTitle, type Mark } from "./placement";

/** "slipped 3 days ago", "due tomorrow", "no deadline". */
export function deadlinePhrase(due: Date | null, now: Date): string {
  if (!due) return "no deadline";
  if (due.getTime() < now.getTime()) {
    const n = -dayDiff(due, now);
    if (n <= 0) return "slipped today";
    return `slipped ${n === 1 ? "1 day" : `${n} days`} ago`;
  }
  return `due ${relDay(due, now)}`;
}

/** The accessible name of a mark: "Reply to Ana, drifting, slipped 3 days ago, 62% sure". */
export function markLabel(m: Mark, now: Date): string {
  const c = m.concern;
  const parts = [shortTitle(c.title), concernStateWords(c), deadlinePhrase(c.due, now)];
  if (c.confidence != null) parts.push(`${pct(c.confidence)} sure`);
  return parts.filter(Boolean).join(", ");
}
