import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { mockMatchMedia } from "@/test/match-media";
import { useReducedMotion } from "./use-reduced-motion";
import { useNarrow } from "./use-narrow";

let mm: ReturnType<typeof mockMatchMedia>;
afterEach(() => mm?.restore());

describe("useReducedMotion", () => {
  it("reads the preference and follows changes", () => {
    mm = mockMatchMedia({ "(prefers-reduced-motion: reduce)": false });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    act(() => mm.set("(prefers-reduced-motion: reduce)", true));
    expect(result.current).toBe(true);
  });
});

describe("useNarrow", () => {
  it("is true at phone width and follows changes", () => {
    mm = mockMatchMedia({ "(max-width: 1023px)": true });
    const { result } = renderHook(() => useNarrow());
    expect(result.current).toBe(true);
    act(() => mm.set("(max-width: 1023px)", false));
    expect(result.current).toBe(false);
  });
});
