/**
 * The idle orb's curious-pet gaze. Pure: `nextGaze` maps (state, input, now) to a new state and the
 * output the orb applies in its idle state only. The orb owns the clock, the randomness (`input.rand`)
 * and the spring; nothing here reads the DOM.
 */

export interface Point {
  x: number;
  y: number;
}

/** Every feel value, with its unit. Nothing else hard-codes a number that changes how the orb behaves. */
export const GAZE_PERSONALITY = {
  /** 0..1: share of the pointer's distance (in orb radii) turned into offset before the clamp. */
  FOLLOW_STRENGTH: 0.8,
  /** Fraction of the orb radius the dense core may shift. */
  MAX_OFFSET: 0.18,
  /** ms the orb watches one spot before losing interest; chosen per glance from `input.rand`. */
  ATTENTION_SPAN_MS: { min: 2000, max: 4000 },
  /** ms on one spot before it peers. */
  PEER_DELAY_MS: 1000,
  /** Fraction of the radius added to the offset while peering. */
  PEER_LEAN: 0.05,
  /** 0..1 added to core brightness while peering or perking up (kept at or below 0.1). */
  PEER_BRIGHTEN: 0.08,
  /** Pointer speed, CSS px per second, above which a flick startles it. */
  STARTLE_SPEED: 2500,
  /** ms before another startle may fire. */
  STARTLE_COOLDOWN_MS: 1500,
  /** Orb radii between the watched spot and a new target for the switch to count (blink). */
  SWITCH_DISTANCE: 1.5,
  /** Orb radii of drift below which a new target is the same spot. */
  SAME_SPOT: 0.35,
  /** ms of no input before it dozes. */
  DOZE_AFTER_MS: 60_000,
  /** Multiplier on breath frequency while dozing. */
  DOZE_BREATH: 0.5,
  /** 0..1 brightness reduction while dozing (at most 0.2: dozing is never mistaken for error). */
  DOZE_DIM: 0.15,
  /** ms spent easing back to centre before the orb counts as centred. */
  RETURN_MS: 700,
  /** ms of the perk-up when input wakes a dozing orb. */
  WAKE_MS: 400,
  /** ms a tap holds its attention; touch glances once, then returns, and never peers. */
  TOUCH_GLANCE_MS: 1500,
  /** Fraction of full lean (0..1) while following; peering leans fully. */
  FOLLOW_LEAN: 0.5,
  /** ms of one blink, and of the gap before the second. */
  BLINK_MS: 120,
  BLINK_GAP_MS: 40,
  /** ms a startle takes to fade, and the fraction the sphere widens at its peak. */
  STARTLE_MS: 250,
  STARTLE_SCALE: 0.06,
  /** Fraction the sphere stretches along the lean axis at full lean (at most 0.03). */
  LEAN_SCALE: 0.03,
  /** 1/s: how fast breath rate and brightness follow the gaze output. */
  RATE_EASE: 2,
  /** Under-damped spring (dampingRatio < 1) for the gaze offset: a small overshoot. */
  GAZE_SPRING: { stiffness: 90, dampingRatio: 0.6 },
} as const;

export type GazePhase = "centered" | "following" | "peering" | "returning" | "dozing" | "waking";

export type PointerKind = "mouse" | "pen" | "touch";

export interface GazeInput {
  /** Whether the orb is in its idle state; any other state gets a neutral gaze. */
  idle: boolean;
  pointer: Point | null;
  /** ms timestamp of the latest pointer event; a new value means new input. */
  pointerAt: number;
  /** CSS px per second at that event. */
  speed: number;
  pointerType: PointerKind;
  /** Centre of the keyboard-focused element, if any. */
  focus: Point | null;
  focusAt: number;
  /** A pending `glance(point)` request. */
  glance: Point | null;
  glanceAt: number;
  orbCenter: Point;
  /** Orb radius in CSS px. */
  orbRadius: number;
  /** 0..1, sampled by the orb when a glance starts; picks the attention span. */
  rand: number;
}

export interface GazeState {
  phase: GazePhase;
  spot: Point | null;
  spotSince: number;
  span: number;
  touch: boolean;
  phaseSince: number;
  lastActivityAt: number;
  lastStartleAt: number;
  handledPointerAt: number;
  handledFocusAt: number;
  handledGlanceAt: number;
}

export interface GazeOutput {
  /** Target offset of the dense core, as a fraction of the orb radius. */
  offset: Point;
  /** Direction of the lean, scaled 0..1; the orb stretches ≤ 3% along it. */
  lean: Point;
  /** Added to core brightness (multiplier is 1 + brightness). */
  brightness: number;
  /** Multiplier on breath frequency. */
  breathRate: number;
  /** One-shot: true on the tick the cue fires. */
  blink: boolean;
  startle: boolean;
}

const ZERO: Point = { x: 0, y: 0 };

export function initialGaze(now: number): GazeState {
  return {
    phase: "centered",
    spot: null,
    spotSince: now,
    span: 0,
    touch: false,
    phaseSince: now,
    lastActivityAt: now,
    lastStartleAt: -Infinity,
    handledPointerAt: 0,
    handledFocusAt: 0,
    handledGlanceAt: 0,
  };
}

const NEUTRAL: GazeOutput = { offset: ZERO, lean: ZERO, brightness: 0, breathRate: 1, blink: false, startle: false };

function spanFor(rand: number): number {
  const { min, max } = GAZE_PERSONALITY.ATTENTION_SPAN_MS;
  return min + Math.min(1, Math.max(0, rand)) * (max - min);
}

function dist(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function direction(from: Point, to: Point): { dir: Point; distance: number } {
  const distance = dist(from, to);
  if (distance < 1e-6) return { dir: ZERO, distance: 0 };
  return { dir: { x: (to.x - from.x) / distance, y: (to.y - from.y) / distance }, distance };
}

export function nextGaze(prev: GazeState, input: GazeInput, now: number): { state: GazeState; out: GazeOutput } {
  const P = GAZE_PERSONALITY;
  let s: GazeState = {
    ...prev,
    handledPointerAt: Math.max(prev.handledPointerAt, input.pointerAt),
    handledFocusAt: Math.max(prev.handledFocusAt, input.focusAt),
    handledGlanceAt: Math.max(prev.handledGlanceAt, input.glanceAt),
  };

  if (!input.idle) {
    // Another state owns the orb; stale input must not fire when idle returns.
    s = { ...s, phase: "centered", spot: null, lastActivityAt: now, phaseSince: now, spotSince: now };
    return { state: s, out: NEUTRAL };
  }

  let blink = false;
  let startle = false;

  // Newest unhandled input wins.
  const events: { at: number; point: Point | null; kind: "pointer" | "focus" | "glance" }[] = [];
  if (input.pointerAt > prev.handledPointerAt && input.pointer) events.push({ at: input.pointerAt, point: input.pointer, kind: "pointer" });
  if (input.focusAt > prev.handledFocusAt && input.focus) events.push({ at: input.focusAt, point: input.focus, kind: "focus" });
  if (input.glanceAt > prev.handledGlanceAt && input.glance) events.push({ at: input.glanceAt, point: input.glance, kind: "glance" });
  events.sort((a, b) => a.at - b.at);

  for (const ev of events) {
    const target = ev.point!;
    const touch = ev.kind === "pointer" && input.pointerType === "touch";
    s = { ...s, lastActivityAt: now };

    if (ev.kind === "pointer" && input.speed > P.STARTLE_SPEED && now - s.lastStartleAt >= P.STARTLE_COOLDOWN_MS) {
      startle = true;
      s = { ...s, lastStartleAt: now };
    }

    if (s.phase === "dozing") {
      s = { ...s, phase: "waking", phaseSince: now, spot: target, spotSince: now, span: touch ? P.TOUCH_GLANCE_MS : spanFor(input.rand), touch };
      continue;
    }
    if (s.phase === "waking") {
      s = { ...s, spot: target };
      continue;
    }
    const watching = s.phase === "following" || s.phase === "peering";
    if (!watching || !s.spot) {
      s = { ...s, phase: "following", phaseSince: now, spot: target, spotSince: now, span: touch ? P.TOUCH_GLANCE_MS : spanFor(input.rand), touch };
      continue;
    }
    const moved = dist(target, s.spot) / input.orbRadius;
    if (moved > P.SWITCH_DISTANCE) {
      blink = true;
      s = { ...s, phase: "following", phaseSince: now, spot: target, spotSince: now, span: touch ? P.TOUCH_GLANCE_MS : spanFor(input.rand), touch };
    } else if (moved > P.SAME_SPOT) {
      // Still looking at roughly the same place, but the pointer is alive: interest renews.
      s = { ...s, phase: "following", phaseSince: now, spot: target, spotSince: now, touch };
    }
  }

  // Time-driven transitions.
  if (s.phase === "waking" && now - s.phaseSince >= P.WAKE_MS) {
    s = { ...s, phase: "following", phaseSince: now, spotSince: now };
  }
  if ((s.phase === "following" || s.phase === "peering") && s.spot) {
    const held = now - s.spotSince;
    if (held >= s.span) {
      s = { ...s, phase: "returning", phaseSince: now, spot: null };
    } else if (s.phase === "following" && !s.touch && held >= P.PEER_DELAY_MS) {
      s = { ...s, phase: "peering", phaseSince: now };
    }
  }
  if (s.phase === "returning" && now - s.phaseSince >= P.RETURN_MS) {
    s = { ...s, phase: "centered", phaseSince: now };
  }
  if (s.phase === "centered" && now - s.lastActivityAt >= P.DOZE_AFTER_MS) {
    s = { ...s, phase: "dozing", phaseSince: now };
  }

  return { state: s, out: outputFor(s, input, blink, startle) };
}

function outputFor(s: GazeState, input: GazeInput, blink: boolean, startle: boolean): GazeOutput {
  const P = GAZE_PERSONALITY;
  const base = { ...NEUTRAL, blink, startle };
  switch (s.phase) {
    case "dozing":
      return { ...base, brightness: -P.DOZE_DIM, breathRate: P.DOZE_BREATH };
    case "centered":
    case "returning":
      return base;
    case "waking":
    case "following":
    case "peering": {
      if (!s.spot) return base;
      const { dir, distance } = direction(input.orbCenter, s.spot);
      const magnitude = P.MAX_OFFSET * Math.min(1, (P.FOLLOW_STRENGTH * distance) / input.orbRadius);
      const peer = s.phase === "peering";
      const perk = s.phase === "waking";
      const mag = magnitude + (peer ? P.PEER_LEAN : 0);
      const lean = peer ? 1 : P.FOLLOW_LEAN;
      return {
        ...base,
        offset: { x: dir.x * mag, y: dir.y * mag },
        lean: { x: dir.x * lean * (magnitude / P.MAX_OFFSET), y: dir.y * lean * (magnitude / P.MAX_OFFSET) },
        brightness: peer || perk ? P.PEER_BRIGHTEN : 0,
      };
    }
  }
}

/** One semi-implicit Euler step of the gaze spring (stiffness k, damping ratio ζ). */
export function stepSpring(
  pos: number,
  vel: number,
  goal: number,
  dt: number,
  spring: { stiffness: number; dampingRatio: number } = GAZE_PERSONALITY.GAZE_SPRING,
): { pos: number; vel: number } {
  const k = spring.stiffness;
  const c = 2 * spring.dampingRatio * Math.sqrt(k);
  const v = vel + (k * (goal - pos) - c * vel) * dt;
  return { pos: pos + v * dt, vel: v };
}
