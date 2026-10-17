import { describe, expect, it } from "vitest";
import { dailyAverages, padDays } from "./days";

const NOW = new Date("2026-10-30T23:30:00-05:00"); // 2026-10-31T04:30Z

describe("padDays", () => {
  it("returns 30 UTC calendar days ending today, zero for missing days", () => {
    const days = padDays([{ date: "2026-10-31", usd: 2, calls: 1 }, { date: "2026-10-01", usd: 1, calls: 1 }], NOW);
    expect(days).toHaveLength(30);
    expect(days[0].date).toBe("2026-10-02");
    expect(days[29]).toEqual({ date: "2026-10-31", usd: 2, calls: 1 });
    expect(days.find((d) => d.date === "2026-10-01")).toBeUndefined();
    expect(days[1]).toEqual({ date: "2026-10-03", usd: 0, calls: 0 });
  });

  it("is all zeros for empty input", () => {
    expect(padDays([], NOW).every((d) => d.usd === 0)).toBe(true);
  });
});

describe("dailyAverages", () => {
  it("divides by calendar days, not by buckets present", () => {
    const days = padDays([{ date: "2026-10-31", usd: 7, calls: 1 }, { date: "2026-10-05", usd: 30, calls: 1 }], NOW);
    const { last7, last30 } = dailyAverages(days, "2026-10-05");
    expect(last7).toBeCloseTo(1);
    expect(last30).toBeCloseTo(37 / 27);
  });

  it("divides by days since the first bucket on a young install", () => {
    const days = padDays([{ date: "2026-10-29", usd: 3, calls: 1 }], NOW);
    const { last7, last30 } = dailyAverages(days, "2026-10-29");
    expect(last30).toBeCloseTo(3 / 3);
    expect(last7).toBeCloseTo(3 / 3);
  });

  it("divides by the full window when the first bucket is older", () => {
    const days = padDays([{ date: "2026-10-31", usd: 30, calls: 1 }], NOW);
    expect(dailyAverages(days, "2026-08-01").last30).toBeCloseTo(1);
  });
});
