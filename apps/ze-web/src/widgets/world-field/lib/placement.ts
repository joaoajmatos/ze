import type { Concern } from "@/shared/lib";

export const W = 920;
export const H = 540;
export const ML = 56;
export const MR = 48;
export const MT = 30;
export const MB = 40;
export const PW = W - ML - MR;
export const PH = H - MT - MB;
export const Y0 = MT;
export const Y1 = MT + PH;
export const NOW_X = ML + PW * 0.2;
/** Concerns that are not claims (goals, relationships, reminders) sit here, at the top of their band. */
export const NOT_A_CLAIM_Y = Y0 + 14;
const LANE_STEP = 18;

export type BandId = "slipped" | "week" | "later" | "none";

export const BANDS: { id: BandId; label: string; from: number; to: number; hot?: boolean }[] = [
  { id: "slipped", label: "Slipped", from: 0, to: 0.2, hot: true },
  { id: "week", label: "This week", from: 0.2, to: 0.52 },
  { id: "later", label: "Later", from: 0.52, to: 0.78 },
  { id: "none", label: "No deadline", from: 0.78, to: 1 },
];

export function bandOf(days: number | null): BandId {
  if (days == null) return "none";
  if (days < 0) return "slipped";
  if (days <= 7) return "week";
  return "later";
}

const DAY = 86_400_000;

/** Days until the deadline, negative once past, null with none. */
export function daysLeft(c: Pick<Concern, "due">, now: Date): number | null {
  return c.due ? (c.due.getTime() - now.getTime()) / DAY : null;
}

/** A slipped concern is in the Slipped band whatever its deadline says; otherwise the deadline decides. */
export function bandOfConcern(c: Pick<Concern, "due" | "slipped">, now: Date): BandId {
  return c.slipped ? "slipped" : bandOf(daysLeft(c, now));
}

export function xOfDays(d: number): number {
  if (d <= 0) return ML + PW * (0.2 * (1 - Math.min(7, -d) / 7));
  if (d <= 7) return ML + PW * (0.2 + 0.32 * (d / 7));
  return ML + PW * (0.52 + 0.26 * Math.min(1, Math.log(d / 7) / Math.log(30 / 7)));
}

export function yOf(conf: number): number {
  return Y0 + PH * (1 - Math.min(1, Math.max(0, conf)));
}

const LABEL_MAX = 36;
const CHAR_W = 7;

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

/** Nudges a label vertically until it clears the labels already placed. */
function place(box: Box, placed: Box[]): Box {
  let best = box;
  for (let step = 0; step < 60; step++) {
    const dy = step === 0 ? 0 : (step % 2 ? 1 : -1) * Math.ceil(step / 2) * (box.h + 1);
    const cand = { ...box, y: box.y + dy };
    if (!placed.some((p) => overlaps(cand, p))) {
      best = cand;
      break;
    }
  }
  placed.push(best);
  return best;
}

/** The part of a title before a colon. */
export function shortTitle(title: string): string {
  const t = title.split(":")[0].trim();
  return t.length > 60 ? `${t.slice(0, 58).trim()}…` : t;
}

export function shortLabel(title: string): string {
  const t = shortTitle(title);
  if (t.length <= LABEL_MAX) return t;
  const cut = t.slice(0, LABEL_MAX + 1);
  const at = cut.lastIndexOf(" ");
  return `${(at > 10 ? cut.slice(0, at) : cut.slice(0, LABEL_MAX)).replace(/[,:;]$/, "")}…`;
}

export interface Mark {
  concern: Concern;
  n: number;
  x: number;
  y: number;
  band: BandId;
  /** Days until the deadline (negative once past), null with none. */
  days: number | null;
  label: string;
  /** Label anchor x and baseline-centre y; the label sits right of the mark when `right`. */
  lx: number;
  ly: number;
  right: boolean;
  box: Box;
}

/**
 * Place every concern: x is time left, y is how sure. Slipped concerns sit in the Slipped band even without a
 * past deadline (spread across it by rank); other concerns with no deadline sit in lanes by rank; concerns with
 * no confidence sit in the not-a-claim lane. `k` converts CSS px to viewBox units so label boxes are px-true.
 */
export function layoutMarks(concerns: Concern[], now: Date, k: number): Mark[] {
  const placed: Box[] = [];
  const lineH = 15 * k;
  const byRank = (a: Concern, b: Concern) => (a.rank ?? Infinity) - (b.rank ?? Infinity);
  const undatedSlipped = concerns.filter((c) => c.slipped && (c.due == null || daysLeft(c, now)! >= 0)).sort(byRank);
  const none = concerns.filter((c) => !c.slipped && c.due == null).sort(byRank);
  const lanes = new Map<BandId, number>();

  return concerns.map((c, i) => {
    const days = daysLeft(c, now);
    const band = bandOfConcern(c, now);
    const noneIndex = none.indexOf(c);
    const slipIndex = undatedSlipped.indexOf(c);
    const x =
      slipIndex >= 0
        ? ML + PW * (0.03 + (0.14 * (slipIndex + 0.5)) / undatedSlipped.length)
        : days == null
          ? ML + PW * (0.8 + (0.18 * (noneIndex + 0.5)) / Math.max(1, none.length))
          : xOfDays(days);

    let y: number;
    if (noneIndex >= 0) y = Y0 + 52 + noneIndex * Math.max(lineH + 6, 22);
    else if (c.confidence == null) {
      const lane = lanes.get(band) ?? 0;
      lanes.set(band, lane + 1);
      y = NOT_A_CLAIM_Y + lane * LANE_STEP;
    } else y = yOf(c.confidence);

    const right = noneIndex >= 0 ? false : x < W - 230 * k;
    const label = shortLabel(c.title);
    const w = label.length * CHAR_W * k;
    const box = place({ x: right ? x + 13 : x - 13 - w, y: y - lineH / 2, w, h: lineH }, placed);
    return { concern: c, n: i + 1, x, y, band, days, label, lx: right ? box.x : box.x + w, ly: box.y + lineH / 2, right, box };
  });
}
