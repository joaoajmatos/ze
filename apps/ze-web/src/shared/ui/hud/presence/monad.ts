/**
 * The monad: the cluster of cream dots at the orb's lit core (about 4x4 of the grid's dots), its eye and
 * the origin of every state. It is made of the grid's own dots, lit cream; moving it moves the lighting
 * across the grid, nothing is drawn on top. Pure helpers only; the orb owns the clock, the canvas and the
 * springs. Positions are sphere units (fractions of the radius).
 */
import { GAZE_PERSONALITY, type GazePhase, type Point } from "./gaze";
import type { OrbState } from "./types";

export const MONAD = {
  /** Radius of the resting cluster in sphere units: about 4x4 dots on the 29-dot grid. */
  EYE_RADIUS: 0.16,
  /** Half a grid pitch: a squashed eye never loses its nearest row of dots. */
  MIN_HALF: 0.034,
  /** Peering lights more dots: the cluster widens by this fraction. */
  PEER_DILATE: 0.25,
  /** A startle shrinks the cluster to fewer dots, by this fraction at its peak. */
  STARTLE_CONTRACT: 0.4,
  /** A blink unlights the cluster's rows vertically by this fraction at its peak (a lid). */
  BLINK_SQUASH: 0.85,
  /** Dozing: the cluster narrows to a dim line, half-closed. */
  DOZE_SQUASH: 0.3,
  DOZE_ALPHA: 0.6,
  /** 1/s: how fast the eye's resting shape follows the state (waking opens over about 250 ms). */
  EYE_EASE: 12,
  /** Fraction of the lean toward a flagged item that the monad takes in attention. */
  ATTENTION_REACH: 0.14,
  /** Gaze deformation around the monad: falloff radius, pull toward it, bulge around the pulled zone, lift. */
  SIGMA: 0.55,
  GATHER: 0.24,
  BULGE: 0.1,
  LIFT: 0.22,
} as const;

/** Keep p inside the sphere: magnitude at most `max`. */
export function clampPoint(p: Point, max: number = GAZE_PERSONALITY.POINT_MAX): Point {
  const m = Math.hypot(p.x, p.y);
  return m <= max || m === 0 ? p : { x: (p.x / m) * max, y: (p.y / m) * max };
}

/** Where the monad rests: the gaze point, plus a small look toward the flagged item in attention. */
export function monadPosition(gaze: Point, attention: Point): Point {
  return clampPoint({ x: gaze.x + attention.x * MONAD.ATTENTION_REACH, y: gaze.y + attention.y * MONAD.ATTENTION_REACH });
}

/** How far the monad is from the center, 0..1 of POINT_MAX: how strongly the gaze deforms the dots. */
export function gazeStrength(m: Point): number {
  return Math.min(1, Math.hypot(m.x, m.y) / GAZE_PERSONALITY.POINT_MAX);
}

export interface Deformation {
  dx: number;
  dy: number;
  /** Extra brightness: the dots around the eye catch its light. */
  lift: number;
}

/**
 * The gaze deformation of one dot at p (sphere units), centered on the monad m: the dots near it gather
 * toward it, the ring around the gathered zone bulges away, the limb stays round.
 */
export function deform(p: Point, m: Point): Deformation {
  const k = gazeStrength(m);
  if (k === 0) return { dx: 0, dy: 0, lift: 0 };
  const vx = m.x - p.x;
  const vy = m.y - p.y;
  const d = Math.hypot(vx, vy);
  const S = MONAD.SIGMA;
  const r = Math.hypot(p.x, p.y);
  const guard = 1 - Math.min(1, Math.max(0, (r - 0.7) / 0.3)) ** 2;
  const w = Math.exp(-(d * d) / (S * S));
  const ring = Math.exp(-(((d - 1.15 * S) / (0.45 * S)) ** 2));
  const ux = d > 1e-6 ? vx / d : 0;
  const uy = d > 1e-6 ? vy / d : 0;
  // The cluster's own dots stay a crisp grid; the dots around it are the ones that gather.
  const core = Math.min(1, Math.max(0, (d - MONAD.EYE_RADIUS * 0.9) / (MONAD.EYE_RADIUS * 1.3)));
  const pull = MONAD.GATHER * w * k * guard * core * core * (3 - 2 * core);
  const push = MONAD.BULGE * ring * k * guard;
  return { dx: vx * pull - ux * push, dy: vy * pull - uy * push, lift: MONAD.LIFT * w * k };
}

/** Normalized distance (0..1) of a dot's home from the monad: the radius the stagger is measured in. */
export function originRadius(home: Point, m: Point): number {
  return Math.min(1, Math.hypot(home.x - m.x, home.y - m.y) / (1 + Math.hypot(m.x, m.y)));
}

/** The eye's shape: the cluster's scale across and down, the lit dots' opacity, and its tint (above 0.5 it is coral). */
export interface Eye {
  sx: number;
  sy: number;
  alpha: number;
  coral: number;
}

export const OPEN_EYE: Eye = { sx: 1, sy: 1, alpha: 1, coral: 0 };

/** Whether the grid dot at `home` belongs to the monad: inside the eye ellipse around m, at least one row tall. */
export function inEye(home: Point, m: Point, eye: Eye): boolean {
  const rx = Math.max(MONAD.MIN_HALF, MONAD.EYE_RADIUS * eye.sx);
  const ry = Math.max(MONAD.MIN_HALF, MONAD.EYE_RADIUS * eye.sy);
  return ((home.x - m.x) / rx) ** 2 + ((home.y - m.y) / ry) ** 2 <= 1;
}

/** The resting eye for an orb state and gaze phase, before blink and startle. `age` is seconds in the state. */
export function eyeBase(state: OrbState, phase: GazePhase, age: number, tAbs: number): Eye {
  const P = MONAD;
  switch (state) {
    case "idle":
      if (phase === "dozing") return { sx: 1, sy: P.DOZE_SQUASH, alpha: P.DOZE_ALPHA, coral: 0 };
      if (phase === "peering") return { sx: 1 + P.PEER_DILATE, sy: 1 + P.PEER_DILATE, alpha: 1, coral: 0 };
      return OPEN_EYE;
    case "listening":
      return { sx: 1.12, sy: 1.12, alpha: 1, coral: 0 };
    case "speaking": {
      const a = 0.5 + 0.5 * Math.sin(tAbs * 9.1);
      return { sx: 1 + 0.18 * a, sy: 1 + 0.18 * a, alpha: 1, coral: 0 };
    }
    case "attention": {
      const onset = Math.exp(-age * 1.8);
      return { sx: 1 + 0.35 * onset, sy: 1 + 0.35 * onset, alpha: 1, coral: 0.55 + 0.45 * onset };
    }
    case "done": {
      const bloom = Math.exp(-age * 2.2);
      return { sx: 1 + 0.5 * bloom, sy: 1 + 0.5 * bloom, alpha: 1, coral: 0 };
    }
    case "error": {
      const flicker = 0.5 + 0.3 * Math.sin(tAbs * 37) * Math.sin(tAbs * 5.3);
      return { sx: 0.8, sy: 0.8, alpha: flicker, coral: 0 };
    }
    default:
      return OPEN_EYE;
  }
}

/** Ease the resting eye toward its target; `k` is 0..1 per frame. */
export function easeEye(cur: Eye, target: Eye, k: number): Eye {
  return {
    sx: cur.sx + (target.sx - cur.sx) * k,
    sy: cur.sy + (target.sy - cur.sy) * k,
    alpha: cur.alpha + (target.alpha - cur.alpha) * k,
    coral: cur.coral + (target.coral - cur.coral) * k,
  };
}

/** Reflexes on top of the resting eye: blink (0..1) unlights its rows like a lid, startle (0..1) shrinks it. */
export function withReflexes(eye: Eye, blink: number, startle: number): Eye {
  const c = 1 - MONAD.STARTLE_CONTRACT * startle;
  return { sx: eye.sx * c, sy: eye.sy * c * (1 - MONAD.BLINK_SQUASH * blink), alpha: eye.alpha, coral: eye.coral };
}
