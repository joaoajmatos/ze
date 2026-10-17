import { useEffect, useState } from "react";

export const LAST_SEEN_KEY = "ze.world.lastSeenAt";
const DAY_MS = 24 * 60 * 60 * 1000;
const NEW_VISIT_MS = 5 * 60 * 1000;

export function readLastSeen(): Date | null {
  try {
    const raw = localStorage.getItem(LAST_SEEN_KEY);
    if (!raw) return null;
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

function writeLastSeen(now: Date): void {
  try {
    localStorage.setItem(LAST_SEEN_KEY, now.toISOString());
  } catch {
    // Storage is a per-viewer convenience; losing it only widens the next "away" window.
  }
}

export function initialSince(now: Date): Date {
  return readLastSeen() ?? new Date(now.getTime() - DAY_MS);
}

export interface Visit {
  since: Date;
  hiddenAt: Date | null;
}

export type VisitEvent = { type: "hidden"; now: Date } | { type: "visible"; now: Date };

/** `since` moves only when World was hidden long enough to count as a new visit. */
export function nextVisit(visit: Visit, event: VisitEvent): Visit {
  if (event.type === "hidden") return { ...visit, hiddenAt: event.now };
  if (!visit.hiddenAt) return visit;
  const away = event.now.getTime() - visit.hiddenAt.getTime();
  return { since: away >= NEW_VISIT_MS ? visit.hiddenAt : visit.since, hiddenAt: null };
}

/**
 * The time "while you were away" counts from. Storage always holds the last time World was in front of
 * the user; the visit's `since` stays fixed in memory until a new visit starts.
 */
export function useLastSeen(): Date {
  const [visit, setVisit] = useState<Visit>(() => ({ since: initialSince(new Date()), hiddenAt: null }));

  useEffect(() => {
    const onVisibility = () => {
      const now = new Date();
      if (document.visibilityState === "hidden") {
        writeLastSeen(now);
        setVisit((v) => nextVisit(v, { type: "hidden", now }));
      } else {
        setVisit((v) => nextVisit(v, { type: "visible", now }));
      }
    };
    const onPageHide = () => writeLastSeen(new Date());
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", onPageHide);
      writeLastSeen(new Date());
    };
  }, []);

  return visit.since;
}
