import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LAST_SEEN_KEY, initialSince, nextVisit, readLastSeen, useLastSeen } from "./last-seen";

const t = (iso: string) => new Date(iso);
const NOW = t("2026-10-17T12:00:00Z");

describe("readLastSeen / initialSince", () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("reads the stored time", () => {
    localStorage.setItem(LAST_SEEN_KEY, "2026-10-17T08:00:00.000Z");
    expect(initialSince(NOW)).toEqual(t("2026-10-17T08:00:00Z"));
  });

  it("falls back to now minus 24 hours with nothing stored", () => {
    expect(initialSince(NOW)).toEqual(t("2026-10-16T12:00:00Z"));
  });

  it("survives a throwing localStorage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readLastSeen()).toBeNull();
    expect(initialSince(NOW)).toEqual(t("2026-10-16T12:00:00Z"));
  });

  it("falls back on a garbled stored value", () => {
    localStorage.setItem(LAST_SEEN_KEY, "not a date");
    expect(initialSince(NOW)).toEqual(t("2026-10-16T12:00:00Z"));
  });
});

describe("nextVisit", () => {
  const start = { since: t("2026-10-17T08:00:00Z"), hiddenAt: null };

  it("a hide records the hide time and leaves since alone", () => {
    expect(nextVisit(start, { type: "hidden", now: NOW })).toEqual({ since: start.since, hiddenAt: NOW });
  });

  it("a 5-second hide keeps since", () => {
    const hidden = nextVisit(start, { type: "hidden", now: NOW });
    const back = nextVisit(hidden, { type: "visible", now: new Date(NOW.getTime() + 5000) });
    expect(back).toEqual({ since: start.since, hiddenAt: null });
  });

  it("a hide of 5 minutes or more starts a new visit at the hide time", () => {
    const hidden = nextVisit(start, { type: "hidden", now: NOW });
    const back = nextVisit(hidden, { type: "visible", now: new Date(NOW.getTime() + 5 * 60_000) });
    expect(back).toEqual({ since: NOW, hiddenAt: null });
  });

  it("visible without a hide changes nothing", () => {
    expect(nextVisit(start, { type: "visible", now: NOW })).toEqual(start);
  });
});

describe("useLastSeen", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    localStorage.clear();
  });
  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  function setVisibility(state: "hidden" | "visible") {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => state });
    document.dispatchEvent(new Event("visibilitychange"));
  }

  it("writes the time on every hide, on pagehide and on unmount", () => {
    const { result, unmount } = renderHook(() => useLastSeen());
    expect(result.current).toEqual(t("2026-10-16T12:00:00Z"));

    vi.setSystemTime(t("2026-10-17T12:00:05Z"));
    act(() => setVisibility("hidden"));
    expect(localStorage.getItem(LAST_SEEN_KEY)).toBe("2026-10-17T12:00:05.000Z");

    vi.setSystemTime(t("2026-10-17T12:00:10Z"));
    act(() => setVisibility("visible"));
    expect(result.current).toEqual(t("2026-10-16T12:00:00Z"));

    vi.setSystemTime(t("2026-10-17T12:01:00Z"));
    act(() => {
      window.dispatchEvent(new Event("pagehide"));
    });
    expect(localStorage.getItem(LAST_SEEN_KEY)).toBe("2026-10-17T12:01:00.000Z");

    vi.setSystemTime(t("2026-10-17T12:02:00Z"));
    unmount();
    expect(localStorage.getItem(LAST_SEEN_KEY)).toBe("2026-10-17T12:02:00.000Z");
  });

  it("moves since after a hide of five minutes or more", () => {
    const { result } = renderHook(() => useLastSeen());
    act(() => setVisibility("hidden"));
    vi.setSystemTime(new Date(NOW.getTime() + 6 * 60_000));
    act(() => setVisibility("visible"));
    expect(result.current).toEqual(NOW);
  });
});
