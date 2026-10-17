import { act, render } from "@testing-library/react";
import { Profiler, createRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";
import { GAZE_PERSONALITY as P } from "./gaze";
import { Orb } from "./Orb";
import { Presence } from "./Presence";
import type { OrbState, PresenceHandle } from "./types";

const colors = { main: "#b9a3ff", cream: "#efe5d7", coral: "#ff6f63", dim: "#9a90ae" };
const ctxStub = new Proxy({}, { get: () => () => {}, set: () => true });

let frames: FrameRequestCallback[] = [];
let clock = 0;
let mm: ReturnType<typeof mockMatchMedia>;

/** Run queued animation frames, advancing the fake clock by `ms` per frame. */
function step(count: number, ms = 16) {
  for (let i = 0; i < count; i++) {
    const batch = frames;
    frames = [];
    clock += ms;
    act(() => batch.forEach((cb) => cb(clock)));
  }
}

function pointer(type: string, x: number, y: number, pointerType = "mouse") {
  const e = new MouseEvent(type, { clientX: x, clientY: y, bubbles: true });
  Object.defineProperty(e, "pointerType", { value: pointerType });
  act(() => {
    window.dispatchEvent(e);
  });
}

beforeEach(() => {
  frames = [];
  clock = 1000;
  vi.spyOn(performance, "now").mockImplementation(() => clock);
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => frames.push(cb));
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(ctxStub as unknown as CanvasRenderingContext2D);
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  );
  mm = mockMatchMedia({});
});
afterEach(() => {
  mm.restore();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const canvas = (c: HTMLElement) => c.querySelector("canvas")!;

describe("Orb gaze wiring", () => {
  it("follows the pointer without re-rendering React", () => {
    let renders = 0;
    const { container } = render(
      <Profiler id="orb" onRender={() => renders++}>
        <Orb state="idle" size={184} colors={colors} reducedMotion={false} />
      </Profiler>,
    );
    step(2);
    const before = renders;
    for (let i = 0; i < 100; i++) pointer("pointermove", 300 + i, 200);
    step(2);
    expect(renders).toBe(before);
    expect(canvas(container).dataset.gaze).toBe("following");
  });

  it("moves the monad toward the pointer, inside the sphere, and back to centre when the orb is busy", () => {
    const { container, rerender } = render(<Orb state="idle" size={184} colors={colors} reducedMotion={false} />);
    step(1);
    pointer("pointermove", 900, 0);
    step(40);
    const [x] = canvas(container).dataset.monad!.split(" ").map(Number);
    expect(x).toBeGreaterThan(10);
    expect(x).toBeLessThanOrEqual(P.POINT_MAX * 92 + 0.1);
    rerender(<Orb state="thinking" size={184} colors={colors} reducedMotion={false} />);
    step(120);
    expect(Math.abs(Number(canvas(container).dataset.monad!.split(" ")[0]))).toBeLessThan(1);
  });

  it("keeps the monad centred under reduced motion", () => {
    const { container } = render(<Orb state="idle" size={184} colors={colors} reducedMotion />);
    step(2);
    expect(canvas(container).dataset.monad).toBe("0.0 0.0");
  });

  it("registers no gaze listeners under reduced motion", () => {
    const add = vi.spyOn(window, "addEventListener");
    render(<Orb state="idle" size={184} colors={colors} reducedMotion />);
    const types = add.mock.calls.map((c) => c[0]);
    expect(types).not.toContain("pointermove");
    expect(types).not.toContain("pointerdown");
    expect(types).not.toContain("focusin");
  });

  it("removes the listeners when reduced motion turns on at runtime", () => {
    const remove = vi.spyOn(window, "removeEventListener");
    mm.set("(prefers-reduced-motion: reduce)", false);
    const { container } = render(<Presence state="idle" phrase="ready" />);
    step(1);
    pointer("pointermove", 300, 200);
    step(1);
    expect(canvas(container).dataset.gaze).toBe("following");
    act(() => mm.set("(prefers-reduced-motion: reduce)", true));
    expect(remove.mock.calls.map((c) => c[0])).toContain("pointermove");
    expect(canvas(container).dataset.gaze).toBeUndefined();
  });

  it("ignores the pointer while the orb is not idle", () => {
    const { container } = render(<Orb state={"thinking" satisfies OrbState} size={184} colors={colors} reducedMotion={false} />);
    step(2);
    pointer("pointermove", 400, 300);
    step(2);
    expect(canvas(container).dataset.gaze ?? "centered").toBe("centered");
  });

  it("glance() looks at an element", () => {
    const ref = createRef<PresenceHandle>();
    const { container } = render(<Orb ref={ref} state="idle" size={184} colors={colors} reducedMotion={false} />);
    step(2);
    const el = document.createElement("button");
    document.body.appendChild(el);
    act(() => ref.current!.glance(el));
    step(2);
    expect(canvas(container).dataset.gaze).toBe("following");
    el.remove();
  });

  it("returns to centre after the attention span", () => {
    const { container } = render(<Orb state="idle" size={184} colors={colors} reducedMotion={false} />);
    step(1);
    pointer("pointermove", 300, 200);
    step(1);
    expect(canvas(container).dataset.gaze).toBe("following");
    step(Math.ceil((P.ATTENTION_SPAN_MS.max + 100) / 100), 100);
    expect(["returning", "centered"]).toContain(canvas(container).dataset.gaze);
  });

  it("a touch drag is not attention, a tap is", () => {
    const { container } = render(<Orb state="idle" size={184} colors={colors} reducedMotion={false} />);
    step(1);
    pointer("pointermove", 300, 200, "touch");
    step(1);
    expect(canvas(container).dataset.gaze).toBeUndefined();
    pointer("pointerdown", 300, 200, "touch");
    step(1);
    expect(canvas(container).dataset.gaze).toBe("following");
  });
});
