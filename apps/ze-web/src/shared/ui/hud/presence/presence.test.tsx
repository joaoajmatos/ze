import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";
import { Presence, heartbeat, staggerDelay, type OrbState } from ".";

const ctxStub = new Proxy({}, { get: () => () => {}, set: () => true });

let mm: ReturnType<typeof mockMatchMedia>;

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(ctxStub as unknown as CanvasRenderingContext2D);
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  );
});
afterEach(() => {
  mm?.restore();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("heartbeat", () => {
  it("repeats every 2.2 s", () => {
    for (const t of [0.05, 0.3, 1.1]) {
      expect(heartbeat(t + 2.2)).toBeCloseTo(heartbeat(t), 10);
      expect(heartbeat(t + 4.4)).toBeCloseTo(heartbeat(t), 10);
    }
  });

  it("peaks at the first beat", () => {
    expect(heartbeat(0)).toBeCloseTo(1, 5);
    expect(heartbeat(1.5)).toBeLessThan(0.01);
  });
});

describe("staggerDelay", () => {
  it("never exceeds 320 ms and grows from core to rim", () => {
    expect(staggerDelay(1, 0.999)).toBeLessThanOrEqual(320);
    expect(staggerDelay(0, 0)).toBe(0);
    expect(staggerDelay(0.2, 0.5)).toBeLessThan(staggerDelay(0.9, 0.5));
  });
});

describe("Presence", () => {
  it("under reduced motion the orb schedules at most one animation frame", () => {
    mm = mockMatchMedia({ "(prefers-reduced-motion: reduce)": true });
    const raf = vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(performance.now());
      return 1;
    });
    render(<Presence state="idle" phrase="ready" />);
    expect(raf.mock.calls.length).toBeLessThanOrEqual(1);
  });

  it.each<[OrbState, string]>([
    ["attention", "polite"],
    ["done", "polite"],
    ["error", "polite"],
    ["idle", "off"],
    ["thinking", "off"],
    ["speaking", "off"],
    ["listening", "off"],
  ])("%s announces %s", (state, live) => {
    mm = mockMatchMedia({});
    render(<Presence state={state} phrase="the phrase" />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent(live === "polite" ? "the phrase" : "");
    expect(screen.getByText("the phrase", { selector: ".t" })).not.toHaveAttribute("aria-live");
  });

  it("shows Offline in the head only for error", () => {
    mm = mockMatchMedia({});
    const { rerender } = render(<Presence state="idle" phrase="ready" />);
    expect(screen.getByText("Online")).toBeInTheDocument();
    rerender(<Presence state="error" phrase="Offline" />);
    expect(screen.getAllByText("Offline").length).toBeGreaterThan(0);
  });

  it("renders headSlot inside the presence head", () => {
    mm = mockMatchMedia({});
    render(<Presence state="idle" phrase="ready" headSlot={<button type="button">slot</button>} />);
    expect(screen.getByRole("button", { name: "slot" }).closest(".presence-head")).not.toBeNull();
  });

  it("under reduced motion the level getter is never called", () => {
    mm = mockMatchMedia({ "(prefers-reduced-motion: reduce)": true });
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(performance.now());
      return 1;
    });
    const level = vi.fn(() => 0.5);
    render(<Presence state="listening" phrase="listening" level={level} />);
    expect(level).not.toHaveBeenCalled();
  });

  it("in listening with motion allowed one animation frame reads the level once", () => {
    mm = mockMatchMedia({});
    let calls = 0;
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      if (calls++ === 0) cb(performance.now());
      return 1;
    });
    const level = vi.fn(() => 0.5);
    render(<Presence state="listening" phrase="listening" level={level} />);
    expect(level).toHaveBeenCalledTimes(1);
  });
});
