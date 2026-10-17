import { describe, expect, it } from "vitest";
import { GAZE_PERSONALITY as P, initialGaze, nextGaze, stepSpring, type GazeInput, type GazeState } from "./gaze";

const R = 92;
const CENTER = { x: 200, y: 200 };

function input(over: Partial<GazeInput> = {}): GazeInput {
  return {
    idle: true,
    pointer: null,
    pointerAt: 0,
    speed: 0,
    pointerType: "mouse",
    focus: null,
    focusAt: 0,
    glance: null,
    glanceAt: 0,
    orbCenter: CENTER,
    orbRadius: R,
    rand: 0,
    ...over,
  };
}

/** Step the machine through events at given times, returning the last result. */
function at(state: GazeState, now: number, over: Partial<GazeInput> = {}) {
  return nextGaze(state, input(over), now);
}

function pointAt(x: number, y: number, t: number, extra: Partial<GazeInput> = {}): Partial<GazeInput> {
  return { pointer: { x, y }, pointerAt: t, ...extra };
}

const mag = (p: { x: number; y: number }) => Math.hypot(p.x, p.y);

describe("gaze timeline", () => {
  it("starts centered with a neutral output", () => {
    const { state, out } = at(initialGaze(0), 10);
    expect(state.phase).toBe("centered");
    expect(out.offset).toEqual({ x: 0, y: 0 });
    expect(out.breathRate).toBe(1);
  });

  it("follows the pointer and clamps the offset to MAX_OFFSET", () => {
    const { state, out } = at(initialGaze(0), 100, pointAt(1200, 200, 100));
    expect(state.phase).toBe("following");
    expect(out.offset.x).toBeGreaterThan(0);
    expect(mag(out.offset)).toBeLessThanOrEqual(P.MAX_OFFSET + 1e-9);
    expect(mag(out.offset)).toBeCloseTo(P.MAX_OFFSET, 5);
  });

  it("a near pointer gives a smaller offset than a far one", () => {
    const near = at(initialGaze(0), 100, pointAt(CENTER.x + R * 0.5, CENTER.y, 100));
    expect(mag(near.out.offset)).toBeLessThan(P.MAX_OFFSET);
  });

  it("peers after PEER_DELAY_MS on the same spot", () => {
    let r = at(initialGaze(0), 100, pointAt(500, 200, 100));
    r = at(r.state, 100 + P.PEER_DELAY_MS - 1, pointAt(500, 200, 100));
    expect(r.state.phase).toBe("following");
    r = at(r.state, 100 + P.PEER_DELAY_MS, pointAt(500, 200, 100));
    expect(r.state.phase).toBe("peering");
    expect(r.out.brightness).toBeGreaterThan(0);
    expect(r.out.brightness).toBeLessThanOrEqual(0.1);
    expect(mag(r.out.offset)).toBeGreaterThan(P.MAX_OFFSET - 1e-9);
    expect(mag(r.out.offset)).toBeLessThanOrEqual(P.MAX_OFFSET + P.PEER_LEAN + 1e-9);
  });

  it("loses interest after the shortest span (rand 0) and the longest (rand 1), then returns to centre", () => {
    for (const [rand, span] of [
      [0, P.ATTENTION_SPAN_MS.min],
      [1, P.ATTENTION_SPAN_MS.max],
    ] as const) {
      let r = at(initialGaze(0), 100, pointAt(500, 200, 100, { rand }));
      r = at(r.state, 100 + span - 1, pointAt(500, 200, 100, { rand }));
      expect(r.state.phase, `rand ${rand} before span`).not.toBe("returning");
      r = at(r.state, 100 + span, pointAt(500, 200, 100, { rand }));
      expect(r.state.phase, `rand ${rand} at span`).toBe("returning");
      expect(r.out.offset).toEqual({ x: 0, y: 0 });
      r = at(r.state, 100 + span + P.RETURN_MS, pointAt(500, 200, 100, { rand }));
      expect(r.state.phase).toBe("centered");
    }
  });

  it("a small drift renews interest; a pointer that rests then goes quiet is dropped", () => {
    let r = at(initialGaze(0), 100, pointAt(500, 200, 100));
    r = at(r.state, 1900, pointAt(500 + R * 0.5, 200, 1900));
    expect(r.state.phase).toBe("following");
    r = at(r.state, 1900 + P.ATTENTION_SPAN_MS.min - 1, pointAt(500 + R * 0.5, 200, 1900));
    expect(r.state.phase).not.toBe("returning");
  });

  it("startles once on a fast flick", () => {
    let r = at(initialGaze(0), 100, pointAt(500, 200, 100, { speed: P.STARTLE_SPEED + 1 }));
    expect(r.out.startle).toBe(true);
    r = at(r.state, 116, pointAt(500, 200, 100, { speed: P.STARTLE_SPEED + 1 }));
    expect(r.out.startle).toBe(false);
    r = at(r.state, 132, pointAt(510, 200, 132, { speed: P.STARTLE_SPEED + 1 }));
    expect(r.out.startle).toBe(false);
  });

  it("does not startle at ordinary speed", () => {
    const r = at(initialGaze(0), 100, pointAt(500, 200, 100, { speed: P.STARTLE_SPEED - 1 }));
    expect(r.out.startle).toBe(false);
  });

  it("blinks once when the target switches beyond SWITCH_DISTANCE", () => {
    let r = at(initialGaze(0), 100, pointAt(300, 200, 100));
    expect(r.out.blink).toBe(false);
    const far = 300 + R * (P.SWITCH_DISTANCE + 0.1);
    r = at(r.state, 200, pointAt(far, 200, 200));
    expect(r.out.blink).toBe(true);
    r = at(r.state, 216, pointAt(far, 200, 200));
    expect(r.out.blink).toBe(false);
  });

  it("does not blink for a switch inside SWITCH_DISTANCE", () => {
    let r = at(initialGaze(0), 100, pointAt(300, 200, 100));
    r = at(r.state, 200, pointAt(300 + R * (P.SWITCH_DISTANCE - 0.2), 200, 200));
    expect(r.out.blink).toBe(false);
  });

  it("dozes after DOZE_AFTER_MS of no input, dimly and never to the error look", () => {
    let r = at(initialGaze(0), P.DOZE_AFTER_MS - 1);
    expect(r.state.phase).toBe("centered");
    r = at(r.state, P.DOZE_AFTER_MS);
    expect(r.state.phase).toBe("dozing");
    expect(r.out.breathRate).toBe(P.DOZE_BREATH);
    expect(1 + r.out.brightness).toBeGreaterThanOrEqual(0.8);
    expect(r.out.offset).toEqual({ x: 0, y: 0 });
    expect(Object.keys(r.out).sort()).toEqual(["blink", "breathRate", "brightness", "lean", "offset", "startle"]);
  });

  it("keeps dozing inside the personality limits", () => {
    expect(P.DOZE_DIM).toBeLessThanOrEqual(0.2);
    expect(P.PEER_BRIGHTEN).toBeLessThanOrEqual(0.1);
    expect(P.GAZE_SPRING.dampingRatio).toBeLessThan(1);
  });

  it("wakes on input with a perk-up, then follows", () => {
    let r = at(initialGaze(0), P.DOZE_AFTER_MS);
    r = at(r.state, P.DOZE_AFTER_MS + 10, pointAt(500, 200, P.DOZE_AFTER_MS + 10));
    expect(r.state.phase).toBe("waking");
    expect(r.out.brightness).toBeGreaterThan(0);
    r = at(r.state, P.DOZE_AFTER_MS + 10 + P.WAKE_MS, pointAt(500, 200, P.DOZE_AFTER_MS + 10));
    expect(r.state.phase).toBe("following");
  });

  it("glance(point) makes it look at that point", () => {
    const r = at(initialGaze(0), 100, { glance: { x: 600, y: 200 }, glanceAt: 100 });
    expect(r.state.phase).toBe("following");
    expect(r.out.offset.x).toBeGreaterThan(0);
  });

  it("follows keyboard focus", () => {
    const r = at(initialGaze(0), 100, { focus: { x: 200, y: 600 }, focusAt: 100 });
    expect(r.out.offset.y).toBeGreaterThan(0);
  });

  it("touch glances at the tap, never peers, then returns", () => {
    let r = at(initialGaze(0), 100, pointAt(600, 200, 100, { pointerType: "touch" }));
    r = at(r.state, 100 + P.PEER_DELAY_MS + 50, pointAt(600, 200, 100, { pointerType: "touch" }));
    expect(r.state.phase).toBe("following");
    r = at(r.state, 100 + P.TOUCH_GLANCE_MS, pointAt(600, 200, 100, { pointerType: "touch" }));
    expect(r.state.phase).toBe("returning");
  });

  it("is neutral when the orb is not idle, and ignores input that arrived meanwhile", () => {
    let r = at(initialGaze(0), 100, pointAt(500, 200, 100));
    r = at(r.state, 200, { ...pointAt(700, 200, 200), idle: false });
    expect(r.out.offset).toEqual({ x: 0, y: 0 });
    expect(r.out.blink).toBe(false);
    expect(r.state.phase).toBe("centered");
    // idle again with the same stale pointer event: nothing new, stays centred
    r = at(r.state, 300, pointAt(700, 200, 200));
    expect(r.state.phase).toBe("centered");
  });

  it("does not doze right after returning to idle", () => {
    let r = at(initialGaze(0), P.DOZE_AFTER_MS - 10, { idle: false });
    r = at(r.state, P.DOZE_AFTER_MS + 10);
    expect(r.state.phase).toBe("centered");
  });
});

describe("stepSpring", () => {
  it("converges and overshoots a little (under-damped)", () => {
    let pos = 0;
    let vel = 0;
    let peak = 0;
    for (let i = 0; i < 600; i++) {
      ({ pos, vel } = stepSpring(pos, vel, 1, 1 / 60));
      peak = Math.max(peak, pos);
    }
    expect(pos).toBeCloseTo(1, 2);
    expect(peak).toBeGreaterThan(1.02);
    expect(peak).toBeLessThan(1.2);
  });
});
