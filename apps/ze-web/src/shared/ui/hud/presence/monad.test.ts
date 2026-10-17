import { describe, expect, it } from "vitest";
import { GAZE_PERSONALITY as G } from "./gaze";
import { MONAD, clampPoint, deform, easeEye, eyeBase, gazeStrength, inEye, monadPosition, originRadius, withReflexes } from "./monad";

describe("monad position", () => {
  it("never leaves the sphere, even when a spring overshoots", () => {
    const p = clampPoint({ x: 2, y: -2 });
    expect(Math.hypot(p.x, p.y)).toBeCloseTo(G.POINT_MAX, 9);
    expect(p.x).toBeGreaterThan(0);
    expect(p.y).toBeLessThan(0);
  });
  it("leaves a point inside the clamp untouched", () => {
    expect(clampPoint({ x: 0.1, y: 0.2 })).toEqual({ x: 0.1, y: 0.2 });
  });
  it("looks a little toward the flagged item in attention, still clamped", () => {
    const m = monadPosition({ x: 0, y: 0 }, { x: 1, y: 0 });
    expect(m.x).toBeCloseTo(MONAD.ATTENTION_REACH, 9);
    expect(Math.hypot(monadPosition({ x: 0.5, y: 0 }, { x: 1, y: 0 }).x, 0)).toBeLessThanOrEqual(G.POINT_MAX + 1e-9);
  });
  it("the gaze strength is 0 at the center and 1 at the clamp", () => {
    expect(gazeStrength({ x: 0, y: 0 })).toBe(0);
    expect(gazeStrength({ x: G.POINT_MAX, y: 0 })).toBeCloseTo(1, 9);
  });
});

describe("deformation is centered on the point", () => {
  const m = { x: 0.4, y: -0.2 };
  it("is zero when the monad rests at the center", () => {
    expect(deform({ x: 0.3, y: 0.3 }, { x: 0, y: 0 })).toEqual({ dx: 0, dy: 0, lift: 0 });
  });
  it("pulls neighbours toward the point, from every side", () => {
    for (const [x, y] of [[0.2, -0.2], [0.6, -0.2], [0.4, 0], [0.4, -0.4]]) {
      const d = deform({ x, y }, m);
      const toward = d.dx * (m.x - x) + d.dy * (m.y - y);
      expect(toward, `${x},${y}`).toBeGreaterThan(0);
    }
  });
  it("is symmetric around the point: opposite neighbours move equally and oppositely", () => {
    const a = deform({ x: m.x + 0.2, y: m.y }, m);
    const b = deform({ x: m.x - 0.2, y: m.y }, m);
    expect(a.dx).toBeCloseTo(-b.dx, 9);
    expect(a.lift).toBeCloseTo(b.lift, 9);
  });
  it("does not move a dot that sits on the point", () => {
    const d = deform(m, m);
    expect(d.dx).toBeCloseTo(0, 9);
    expect(d.dy).toBeCloseTo(0, 9);
  });
  it("bulges the ring around the gathered zone away from the point", () => {
    const d = deform({ x: m.x + 1.15 * MONAD.SIGMA, y: m.y }, m);
    expect(d.dx).toBeGreaterThan(-1e-3);
  });
  it("keeps the limb round: the rim barely moves", () => {
    const d = deform({ x: 0.98, y: 0 }, m);
    expect(Math.hypot(d.dx, d.dy)).toBeLessThan(0.01);
  });
  it("lights the dots nearest the eye the most", () => {
    expect(deform({ x: m.x + 0.05, y: m.y }, m).lift).toBeGreaterThan(deform({ x: m.x + 0.8, y: m.y }, m).lift);
  });
});

describe("stagger origin", () => {
  it("is 0 at the point and grows outward from it, not from the center", () => {
    const m = { x: 0.4, y: 0 };
    expect(originRadius(m, m)).toBe(0);
    expect(originRadius({ x: 0, y: 0 }, m)).toBeGreaterThan(0);
    expect(originRadius({ x: 0.4, y: 0.1 }, m)).toBeLessThan(originRadius({ x: -0.6, y: 0 }, m));
  });
  it("matches the center measure when the point rests there", () => {
    expect(originRadius({ x: 0.6, y: 0.8 }, { x: 0, y: 0 })).toBeCloseTo(1, 9);
  });
});

describe("eye states", () => {
  const open = eyeBase("idle", "centered", 0, 0);
  it("is always present: every state has a visible disc", () => {
    for (const s of ["idle", "listening", "thinking", "speaking", "assembling", "attention", "acting", "done", "error"] as const) {
      const e = eyeBase(s, "centered", 0.5, 0.3);
      expect(e.alpha, s).toBeGreaterThan(0.1);
      expect(e.sx * e.sy, s).toBeGreaterThan(0.3);
    }
  });
  it("dilates when peering", () => {
    expect(eyeBase("idle", "peering", 0, 0).sx).toBeGreaterThan(open.sx);
  });
  it("contracts on a startle", () => {
    expect(withReflexes(open, 0, 1).sx).toBeLessThan(open.sx);
  });
  it("squashes vertically like a lid on a blink, and recovers", () => {
    const b = withReflexes(open, 1, 0);
    expect(b.sy).toBeLessThan(0.2);
    expect(b.sx).toBe(open.sx);
    expect(withReflexes(open, 0, 0)).toEqual(open);
  });
  it("is half-closed and dim when dozing, never fully gone", () => {
    const d = eyeBase("idle", "dozing", 0, 0);
    expect(d.sy).toBeCloseTo(MONAD.DOZE_SQUASH, 9);
    expect(d.sy).toBeLessThan(0.5);
    expect(d.alpha).toBeLessThan(1);
    expect(d.alpha).toBeGreaterThan(0.4);
  });
  it("opens on waking by easing back to the open eye", () => {
    let e = eyeBase("idle", "dozing", 0, 0);
    for (let i = 0; i < 30; i++) e = easeEye(e, eyeBase("idle", "waking", 0, 0), 0.2);
    expect(e.sy).toBeCloseTo(1, 1);
    expect(e.alpha).toBeCloseTo(1, 1);
  });
  it("flares coral at the onset of attention, then keeps a coral ember", () => {
    expect(eyeBase("attention", "centered", 0, 0).coral).toBeGreaterThan(0.9);
    const hold = eyeBase("attention", "centered", 10, 0).coral;
    expect(hold).toBeGreaterThan(0.5);
    expect(hold).toBeLessThan(0.6);
  });
  it("flickers and dims in error", () => {
    const alphas = [0, 0.011, 0.023, 0.047, 0.1].map((t) => eyeBase("error", "centered", 1, t).alpha);
    expect(Math.max(...alphas)).toBeLessThan(1);
    expect(new Set(alphas.map((a) => a.toFixed(3))).size).toBeGreaterThan(1);
  });
  it("blooms from the point when done, then settles", () => {
    expect(eyeBase("done", "centered", 0, 0).sx).toBeGreaterThan(1.3);
    expect(eyeBase("done", "centered", 5, 0).sx).toBeCloseTo(1, 2);
  });
});

/** The grid the orb draws: 29 dots across, homes at (i + 0.5 - 14.5) / 14.5. */
function litDots(m: { x: number; y: number }, eye = eyeBase("idle", "centered", 0, 0)) {
  const out: { x: number; y: number }[] = [];
  for (let j = 0; j < 29; j++)
    for (let i = 0; i < 29; i++) {
      const home = { x: (i + 0.5 - 14.5) / 14.5, y: (j + 0.5 - 14.5) / 14.5 };
      if (Math.hypot(home.x, home.y) <= 1 && inEye(home, m, eye)) out.push(home);
    }
  return out;
}

describe("the monad is a cluster of the grid's own dots", () => {
  it("lights about a 4x4 cluster of the existing dots at rest", () => {
    const n = litDots({ x: 0, y: 0 }).length;
    expect(n).toBeGreaterThanOrEqual(12);
    expect(n).toBeLessThanOrEqual(21);
  });
  it("moves across the grid with the point: different dots, same count", () => {
    const a = litDots({ x: 0, y: 0 });
    const b = litDots({ x: 0.4, y: -0.2 });
    expect(Math.abs(a.length - b.length)).toBeLessThanOrEqual(4);
    const cx = b.reduce((s, p) => s + p.x, 0) / b.length;
    const cy = b.reduce((s, p) => s + p.y, 0) / b.length;
    expect(cx).toBeCloseTo(0.4, 1);
    expect(cy).toBeCloseTo(-0.2, 1);
  });
  it("lights a few more dots when peering and fewer when startled", () => {
    const rest = litDots({ x: 0, y: 0 }).length;
    expect(litDots({ x: 0, y: 0 }, eyeBase("idle", "peering", 0, 0)).length).toBeGreaterThan(rest);
    expect(litDots({ x: 0, y: 0 }, withReflexes(eyeBase("idle", "centered", 0, 0), 0, 1)).length).toBeLessThan(rest);
  });
  it("a blink unlights rows down to one, a doze leaves a thin line, never none", () => {
    const blinked = litDots({ x: 0, y: 0 }, withReflexes(eyeBase("idle", "centered", 0, 0), 1, 0));
    expect(new Set(blinked.map((p) => p.y.toFixed(3))).size).toBe(1);
    const doze = litDots({ x: 0, y: 0 }, eyeBase("idle", "dozing", 0, 0));
    expect(doze.length).toBeGreaterThan(0);
    expect(doze.length).toBeLessThan(litDots({ x: 0, y: 0 }).length);
  });
  it("a blink at any vertical position still lights a row", () => {
    const lid = withReflexes(eyeBase("idle", "centered", 0, 0), 1, 0);
    for (let k = 0; k <= 1000; k++) expect(litDots({ x: 0, y: -0.5 + k / 1000 }, lid).length, `y ${k}`).toBeGreaterThan(0);
  });
  it("keeps a cluster at the clamp inside the sphere", () => {
    for (const p of litDots({ x: G.POINT_MAX, y: 0 })) expect(Math.hypot(p.x, p.y)).toBeLessThanOrEqual(1);
  });
});
