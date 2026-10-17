import { describe, expect, it } from "vitest";
import { ago, agoPhrase, dayDiff, pct, relDay } from "./time-format";

const now = new Date(2026, 9, 17, 12, 0);

describe("time-format", () => {
  it("relDay names near days and counts the rest", () => {
    expect(relDay(new Date(2026, 9, 17, 23), now)).toBe("today");
    expect(relDay(new Date(2026, 9, 18, 1), now)).toBe("tomorrow");
    expect(relDay(new Date(2026, 9, 16, 23), now)).toBe("yesterday");
    expect(relDay(new Date(2026, 9, 14), now)).toBe("3 days ago");
    expect(relDay(new Date(2026, 9, 22), now)).toBe("in 5 days");
    expect(dayDiff(new Date(2026, 9, 14), now)).toBe(-3);
  });
  it("ago is short", () => {
    expect(ago(null, now)).toBe("—");
    expect(ago(new Date(now.getTime() - 20_000), now)).toBe("now");
    expect(ago(new Date(now.getTime() - 5 * 60_000), now)).toBe("5m");
    expect(ago(new Date(now.getTime() - 3 * 3_600_000), now)).toBe("3h");
    expect(ago(new Date(now.getTime() - 50 * 3_600_000), now)).toBe("2d");
  });
  it("agoPhrase reads as a phrase", () => {
    expect(agoPhrase(new Date(now.getTime() - 20_000), now)).toBe("just now");
    expect(agoPhrase(new Date(now.getTime() - 3 * 86_400_000), now)).toBe("3 d ago");
    expect(agoPhrase(new Date(now.getTime() - 5 * 60_000), now)).toBe("5 m ago");
    expect(agoPhrase(null, now)).toBe("—");
  });
  it("pct rounds and dashes null", () => {
    expect(pct(0.624)).toBe("62%");
    expect(pct(null)).toBe("—");
  });
});
