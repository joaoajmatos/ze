import { describe, expect, it } from "vitest";
import type { Concern } from "@/shared/lib";
import { BANDS, ML, NOT_A_CLAIM_Y, NOW_X, PW, Y0, Y1, bandOf, layoutMarks, overlaps, shortLabel, xOfDays, yOf } from "./placement";

const now = new Date("2026-10-17T12:00:00Z");
const day = (n: number) => new Date(now.getTime() + n * 86_400_000);

function concern(id: string, extra: Partial<Concern> = {}): Concern {
  return {
    key: `loop:${id}`, kind: "loop", id, title: `Concern ${id}`, rank: null, computedRank: null, overridden: false, override: null,
    pinned: false, state: "active", claimKind: "fact", provenance: "email", confirmed: false, confidence: 0.7, confidencePrior: null,
    due: null, dueLabel: null, slipped: false, partial: false, driftRationale: null, sources: [], updatedAt: null, reminderId: null, progress: null,
    ...extra,
  };
}

describe("x scale", () => {
  it("anchors the bands (ported values)", () => {
    expect(xOfDays(-7)).toBeCloseTo(ML);
    expect(xOfDays(0)).toBeCloseTo(NOW_X);
    expect(xOfDays(7)).toBeCloseTo(ML + PW * 0.52);
    expect(xOfDays(30)).toBeCloseTo(ML + PW * 0.78);
    expect(NOW_X).toBeCloseTo(ML + PW * 0.2);
  });
  it("is monotonic in time left and clamps past a week behind", () => {
    const xs = [-20, -7, -3, 0, 2, 7, 14, 30, 90].map(xOfDays);
    expect([...xs].sort((a, b) => a - b)).toEqual(xs);
    expect(xOfDays(-20)).toBeCloseTo(ML);
  });
  it("bands cover the plot", () => {
    expect(BANDS[0].from).toBe(0);
    expect(BANDS[BANDS.length - 1].to).toBe(1);
    expect(bandOf(-2)).toBe("slipped");
    expect(bandOf(0)).toBe("week");
    expect(bandOf(7)).toBe("week");
    expect(bandOf(8)).toBe("later");
    expect(bandOf(null)).toBe("none");
  });
  it("y runs from sure at the top to unsure at the bottom", () => {
    expect(yOf(1)).toBe(Y0);
    expect(yOf(0)).toBe(Y1);
    expect(yOf(2)).toBe(Y0);
  });
});

describe("layoutMarks", () => {
  it("puts no-deadline concerns in lanes by rank, labels on the left", () => {
    const marks = layoutMarks([concern("b", { rank: 2 }), concern("a", { rank: 1 }), concern("c", { rank: null })], now, 1);
    const none = marks.filter((m) => m.band === "none").sort((p, q) => p.y - q.y);
    expect(none.map((m) => m.concern.id)).toEqual(["a", "b", "c"]);
    expect(none.every((m) => !m.right)).toBe(true);
    expect(new Set(none.map((m) => m.y)).size).toBe(3);
  });

  it("places a mark at its confidence height and its time", () => {
    const [m] = layoutMarks([concern("a", { due: day(3), confidence: 0.62 })], now, 1);
    expect(m.y).toBeCloseTo(yOf(0.62));
    expect(m.x).toBeCloseTo(xOfDays(3));
    expect(m.band).toBe("week");
  });

  it("sits a null-confidence concern in the not-a-claim lane at the top of its band, never at 0.5", () => {
    const marks = layoutMarks([concern("g", { kind: "goal", confidence: null, due: day(3) }), concern("r", { kind: "reminder", confidence: null, due: day(-2) })], now, 1);
    expect(marks[0].y).toBe(NOT_A_CLAIM_Y);
    expect(marks[1].y).toBe(NOT_A_CLAIM_Y);
    expect(NOT_A_CLAIM_Y).toBeLessThan(yOf(0.9));
    expect(marks.every((m) => m.y !== yOf(0.5))).toBe(true);
  });

  it("staggers null-confidence concerns that share a band", () => {
    const marks = layoutMarks([concern("g1", { kind: "goal", confidence: null, due: day(2) }), concern("g2", { kind: "goal", confidence: null, due: day(3) })], now, 1);
    expect(marks[0].y).toBe(NOT_A_CLAIM_Y);
    expect(marks[1].y).toBeGreaterThan(marks[0].y);
  });

  it("never overlaps two label boxes", () => {
    const many = Array.from({ length: 12 }, (_, i) => concern(`c${i}`, { due: day(2), confidence: 0.7, title: `A long concern title number ${i}` }));
    const marks = layoutMarks(many, now, 1.2);
    for (let i = 0; i < marks.length; i++) for (let j = i + 1; j < marks.length; j++) expect(overlaps(marks[i].box, marks[j].box)).toBe(false);
  });

  it("scales label width with k (px-true type)", () => {
    const [a] = layoutMarks([concern("a", { due: day(2) })], now, 1);
    const [b] = layoutMarks([concern("a", { due: day(2) })], now, 2);
    expect(b.box.w).toBeCloseTo(a.box.w * 2);
  });

  it("puts a slipped concern in the Slipped band whatever its deadline says", () => {
    const marks = layoutMarks(
      [
        concern("goal", { kind: "goal", key: "goal:g", slipped: true, confidence: null, due: null, rank: 1 }),
        concern("future", { slipped: true, due: day(4), confidence: 0.6, rank: 2 }),
        concern("past", { slipped: true, due: day(-3), confidence: 0.6, rank: 3 }),
        concern("calm", { due: day(4), confidence: 0.6, rank: 4 }),
      ],
      now,
      1,
    );
    expect(marks.map((m) => m.band)).toEqual(["slipped", "slipped", "slipped", "week"]);
    const slippedEdge = ML + PW * 0.2;
    for (const m of marks.slice(0, 3)) expect(m.x).toBeLessThanOrEqual(slippedEdge);
    expect(marks[0].y).toBe(NOT_A_CLAIM_Y);
  });

  it("numbers marks in order", () => {
    const marks = layoutMarks([concern("a"), concern("b")], now, 1);
    expect(marks.map((m) => m.n)).toEqual([1, 2]);
  });
});

describe("shortLabel", () => {
  it("cuts at the colon and at a word near 36 characters", () => {
    expect(shortLabel("Reply to Ana: she asked about Friday")).toBe("Reply to Ana");
    const long = shortLabel("Finish the quarterly planning document for the whole team");
    expect(long.length).toBeLessThanOrEqual(37);
    expect(long.endsWith("…")).toBe(true);
  });
});
