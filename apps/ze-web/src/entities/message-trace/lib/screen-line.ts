import type { ScreenTraceResponse } from "@myguyze/ze-client";
import { places } from "@/shared/config";

const PLACE_LABEL: Record<string, string> = Object.fromEntries(places.map((p) => [p.id, p.label]));

/** "Asked about: Workflow · Weekly report" for a Chat about this turn, else "Asked from: Doing · …". */
export function screenTraceLine(screen: ScreenTraceResponse | null | undefined): string | null {
  if (!screen) return null;
  const subject = screen.subject?.[0];
  if (screen.origin === "chat_about" && subject) return `Asked about: ${subject}`;
  const place = screen.place ? (PLACE_LABEL[screen.place] ?? screen.place) : null;
  const parts = [place, subject].filter(Boolean);
  return parts.length ? `Asked from: ${parts.join(" · ")}` : null;
}
