import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAskOverlay } from "./ask-overlay";
import { suggestionsFor } from "./suggestions";
import { useChatAbout } from "./useChatAbout";

const ref = { kind: "workflow_execution", id: "e1", parent_id: "w1", label: "Run of Oct 16" };

function at(pathname: string) {
  window.history.pushState({}, "", pathname);
}

function reduceMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduce && query.includes("reduce"), media: query, addEventListener() {}, removeEventListener() {} }));
}

beforeEach(() => {
  useAskOverlay.getState().reset();
  reduceMotion(false);
});
afterEach(() => {
  vi.unstubAllGlobals();
  at("/");
});

describe("useChatAbout", () => {
  it("off Ask opens the overlay with the subject, three suggestions and a focus request", () => {
    at("/doing/workflows/w1");
    const element = document.createElement("div");
    renderHook(() => useChatAbout()).result.current(ref, element);
    const s = useAskOverlay.getState();
    expect(s.open).toBe(true);
    expect(s.explicitContext).toEqual({ origin: "chat_about", subject: [ref] });
    expect(s.about?.suggestions).toEqual(suggestionsFor("workflow_execution"));
    expect(s.about?.suggestions).toHaveLength(3);
    expect(s.focusTick).toBe(1);
    expect(s.glanceTarget).toBe(element);
  });

  it("on Ask it sets the composer subject and leaves the overlay closed", () => {
    at("/ask/t1");
    renderHook(() => useChatAbout()).result.current(ref, document.body);
    const s = useAskOverlay.getState();
    expect(s.open).toBe(false);
    expect(s.about?.ref).toEqual(ref);
    expect(s.focusTick).toBe(1);
  });

  it("skips the glance under reduced motion", () => {
    reduceMotion(true);
    at("/mind");
    renderHook(() => useChatAbout()).result.current(ref, document.body);
    expect(useAskOverlay.getState().glanceTick).toBe(0);
  });
});

describe("suggestions", () => {
  it("has three questions per kind, with a default, in English and Portuguese", () => {
    for (const kind of ["workflow_execution", "goal", "loop", "mystery"]) {
      expect(suggestionsFor(kind, "en")).toHaveLength(3);
      expect(suggestionsFor(kind, "pt")).toHaveLength(3);
    }
    expect(suggestionsFor("mystery", "en")).toEqual(suggestionsFor("anything else", "en"));
    expect(suggestionsFor("goal", "pt")[0]).not.toBe(suggestionsFor("goal", "en")[0]);
  });
});
