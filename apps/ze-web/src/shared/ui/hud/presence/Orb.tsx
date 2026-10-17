import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { GAZE_PERSONALITY, initialGaze, nextGaze, stepSpring, type GazeInput, type GazeState, type Point, type PointerKind } from "./gaze";
import { simplex2 } from "./noise";
import type { OrbColors, OrbState, PresenceHandle } from "./types";

/** The three palettes' leads (ultraviolet, amethyst, orchid); the orb blends them in oklab while thinking and acting. */
const TONES: [string, string, string] = ["#9e82ff", "#c08cff", "#b9a3ff"];

interface Props {
  state: OrbState;
  size: number;
  /** CSS colors resolved by the caller from the palette. */
  colors: OrbColors;
  reducedMotion: boolean;
  /** Running goals + workflows; one faint orbit ring each while acting. */
  rings?: number;
  /** CSS selector of the thing the orb leans toward while in attention (the slipping item's mark). */
  leanTo?: string;
  label?: string;
}

const N = 29; // dots across the sphere's diameter
const PAD = 7; // extra dot columns of room around the sphere for thrown dots and orbit rings
const STAGGER_MS = 320; // a state change reaches the rim this long after the core
const K = 110; // spring stiffness; damping is critical, so dots never ring
const EYE_R = 0.13; // home radius of the eye: the monad every white animation springs from
const BEAT_S = 2.2; // calm heartbeat period, shared with the mark's CSS pulse

/** Two-beat heart on an absolute clock, so the field mark can pulse in sync. */
export function heartbeat(tAbs: number): number {
  const b = tAbs % BEAT_S;
  return Math.exp(-b * 6) + (b > 0.28 ? 0.5 * Math.exp(-(b - 0.28) * 6) : 0);
}

/** How long after the core a dot at normalized radius r (0..1) with seed (0..1) follows a state change. */
export function staggerDelay(r: number, seed: number): number {
  return (r * 0.75 + seed * 0.25) * STAGGER_MS;
}

type RGB = [number, number, number];
type Lab = [number, number, number];
/** color: 0 main, 1 cream, 2 coral, 3 dim. g (0..2) instead blends ultraviolet → amethyst → orchid. */
type Target = { dx: number; dy: number; v: number; color: 0 | 1 | 2 | 3; g?: number };

// sRGB ↔ oklab (Björn Ottosson), so tone blends never pass through muddy mid-greys.
function toLab([r8, g8, b8]: RGB): Lab {
  const lin = (c: number) => {
    const v = c / 255;
    return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  const r = lin(r8), g = lin(g8), b = lin(b8);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
function toRgb([L, a, b]: Lab): RGB {
  const l = Math.pow(L + 0.3963377774 * a + 0.2158037573 * b, 3);
  const m = Math.pow(L - 0.1055613458 * a - 0.0638541728 * b, 3);
  const s = Math.pow(L - 0.0894841775 * a - 1.291485548 * b, 3);
  const gam = (c: number) => {
    const v = Math.max(0, Math.min(1, c));
    return 255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(v, 1 / 2.4) - 0.055);
  };
  return [gam(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s), gam(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s), gam(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s)];
}
const TONE_LAB: Lab[] = TONES.map((h) => toLab(hexToRgb(h)));
function toneAt(g: number): Lab {
  const k = Math.max(0, Math.min(1.999, g));
  const i = Math.floor(k);
  const f = k - i;
  const A = TONE_LAB[i], B = TONE_LAB[i + 1];
  return [A[0] + (B[0] - A[0]) * f, A[1] + (B[1] - A[1]) * f, A[2] + (B[2] - A[2]) * f];
}

interface Dot {
  x: number; // home, sphere-normalized
  y: number;
  r: number;
  ang: number;
  z: number;
  seed: number;
  col: number; // grid column, for the voice waveform
  dx: number; // current displacement, sphere units
  dy: number;
  vx: number;
  vy: number;
  v: number; // current brightness
  vv: number;
  lab: Lab;
  lastColor: number;
  following: OrbState;
  switchAt: number;
}

type Lean = { x: number; y: number };

function hexToRgb(hex: string): RGB {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Cheap deterministic noise for the voice waveform. */
function wave(i: number, t: number): number {
  return Math.abs(0.55 * Math.sin(i * 0.9 + t * 9.1) + 0.3 * Math.sin(i * 1.7 - t * 13.7) + 0.15 * Math.sin(i * 3.1 + t * 21.3));
}

/**
 * The lit dotted sphere is the home shape in every state. Each program returns where this dot wants
 * to be (a displacement from its grid home), how bright, and which colour; springs do the rest.
 */
function program(s: OrbState, d: Dot, shade: number, rim: number, t: number, age: number, tAbs: number, lean: Lean): Target {
  const target = programFor(s, d, shade, rim, t, age, tAbs, lean);
  // The eye is the dense core. It moves with the gaze parallax and stays lit and white through every
  // state but attention (it turns coral) and error (it goes dim), so each white animation reads as
  // coming out of it.
  if (d.r < EYE_R && s !== "attention" && s !== "error") {
    return { dx: target.dx, dy: target.dy, v: Math.max(target.v, 1 - 0.3 * (d.r / EYE_R)), color: 1 };
  }
  return target;
}

function programFor(s: OrbState, d: Dot, shade: number, rim: number, t: number, age: number, tAbs: number, lean: Lean): Target {
  const { x, y, r, ang, z, seed } = d;
  // Life shared by every state: a slow breath, a ripple that crosses the sphere, and a limb that wobbles.
  const breath = 0.018 * Math.sin(t * 0.9 + r * 1.2);
  const ripple = 0.014 * Math.sin(r * 8.5 - t * 1.6) * (1 - 0.5 * r);
  const wobble = r > 0.72 ? 0.05 * (r - 0.72) / 0.28 * simplex2(Math.cos(ang) * 1.3 + 7, Math.sin(ang) * 1.3 + t * 0.45) : 0;
  const radial = breath + ripple + wobble;
  let dx = x * radial;
  let dy = y * radial;
  const base = shade * 0.8 + rim;
  switch (s) {
    case "idle":
      return { dx, dy, v: base, color: 0 };
    case "listening": {
      // Gathers a little and leans toward the Ask field below; a ring runs inward like it is drawing breath.
      const ring = Math.pow(Math.max(0, Math.sin((r + t * 0.9) * 9)), 10);
      dx += x * -0.07;
      dy += y * -0.05 + 0.05;
      // Tones run edge to core: ultraviolet at the limb, orchid at the centre.
      return { dx, dy, v: shade * 0.45 + rim * 0.6 + ring * 0.9, color: ring > 0.5 ? 1 : 0, g: ring > 0.5 ? undefined : (1 - r) * 2 };
    }
    case "thinking": {
      // Slow internal swirl: the core turns one way, the mid-depth the other, the limb stays put.
      const swirl = 0.16 * (1 - r) * Math.sin(t * 0.55 + seed * 2) * (r < 0.45 ? 1 : -0.6);
      dx += -y * swirl;
      dy += x * swirl;
      const scan = Math.pow(Math.max(0, Math.cos(ang - t * 2.2 - r * 3.2)), 14) * (1 - 0.35 * r);
      // The three tones swirl slowly with the dots.
      const g = 1 + Math.sin(ang * 2 + r * 3.5 - t * 0.7);
      return { dx, dy, v: shade * 0.4 + rim * 0.5 + scan * 0.95 * z, color: scan > 0.6 ? 1 : 0, g: scan > 0.6 ? undefined : g };
    }
    case "speaking": {
      // The sphere pulses with the voice; the waveform crosses its equator.
      const a = wave(d.col, t);
      const pulse = 0.05 * a;
      dx += x * pulse;
      dy += y * pulse;
      const amp = 0.12 + 0.62 * a * Math.sqrt(Math.max(0, 1 - x * x));
      const inBand = Math.abs(y) <= amp;
      // The ripples that cross the sphere carry the tones; the voice band's core stays cream.
      const coreBand = inBand && Math.abs(y) < amp * 0.35 && Math.abs(x) < 0.25 + 0.75 * a;
      return { dx, dy, v: shade * 0.42 + (inBand ? 0.92 : 0), color: coreBand ? 1 : 0, g: coreBand ? undefined : 1 + Math.sin(r * 8.5 - t * 1.6) };
    }
    case "assembling": {
      // A few dots are thrown outward along their own spoke and pulled back; the rest tighten.
      const thrown = seed < 0.09 && r > 0.35;
      if (thrown) {
        const phase = Math.max(0, Math.sin(t * 1.6 + seed * 70));
        const out = 0.9 * Math.pow(phase, 1.5);
        return { dx: Math.cos(ang) * out + dx, dy: Math.sin(ang) * out + dy, v: 0.55 + 0.45 * phase, color: phase > 0.6 ? 1 : 0 };
      }
      const squeeze = -0.06 + 0.03 * Math.sin(t * 2.4);
      dx += x * squeeze;
      dy += y * squeeze;
      return { dx, dy, v: shade * 0.6 + rim * 0.8, color: 0 };
    }
    case "attention": {
      // Onset: the core flares and a shockwave ring runs out through the dots. Hold: a faint coral
      // core on a calm heartbeat, leaning toward the slipping item with a stream of dots to it.
      const onset = Math.exp(-age * 1.8);
      const ringR = age * 1.5;
      const ring = age < 1.3 ? Math.exp(-Math.pow((r - ringR) / 0.13, 2)) : 0;
      const b = heartbeat(tAbs);
      const radialA = 0.022 * b + 0.07 * ring + 0.03 * onset;
      dx += x * radialA + lean.x * (0.05 + 0.02 * b);
      dy += y * radialA + lean.y * (0.05 + 0.02 * b);
      if (seed < 0.045 && r > 0.5 && (lean.x || lean.y)) {
        // Dots leave the core on the beat and stay dark until they have sprung home at wrap.
        const ph = (tAbs / BEAT_S + seed * 40) % 1;
        const reach = 0.95 + ph * 1.5;
        return { dx: lean.x * reach - x, dy: lean.y * reach - y, v: 0.75 * Math.min(1, ph * 6) * (1 - ph) * (1 - 0.5 * onset), color: 2 };
      }
      const core = Math.max(0, 1 - r * 1.9);
      const v = shade * 0.75 + rim * 0.6 + ring * 0.9 + core * (0.6 * onset + 0.12 + 0.18 * b);
      // Coral floods the core at onset and shrinks to a faint ember (r < 0.17) that breathes with the beat.
      const coral = ring > 0.3 || r < 0.17 + 0.3 * onset + 0.05 * b;
      return { dx, dy, v, color: coral ? 2 : 0 };
    }
    case "acting": {
      // A working arc orbits the equator; it never claims a percentage.
      const onBelt = Math.abs(r - 0.92) < 0.07;
      const arc = onBelt ? Math.pow(Math.max(0, Math.cos(ang - t * 3.1)), 3) : 0;
      // A spoke runs from the eye to the arc's head, so the arc reads as sent out by the eye.
      const spoke = r < 0.92 ? Math.pow(Math.max(0, Math.cos(ang - t * 3.1)), 60) * (1 - r) : 0;
      return { dx, dy, v: shade * 0.55 + rim * 0.4 + Math.max(arc, spoke * 0.8), color: arc > 0.5 || spoke > 0.3 ? 1 : 0 };
    }
    case "done": {
      // One bloom outward that settles back over about a second.
      const bloom = Math.exp(-age * 2.2);
      dx += x * 0.1 * bloom;
      dy += y * 0.1 * bloom;
      return { dx, dy, v: base + bloom * (1 - r * 0.6), color: bloom * (1 - r) > 0.35 ? 1 : 0 };
    }
    case "error": {
      const flicker = 0.85 + 0.15 * Math.sin(t * 37) * Math.sin(t * 5.3);
      const jitter = 0.012 * simplex2(seed * 40, t * 6);
      const limb = Math.abs(r - 0.97) < 0.05 ? 0.62 : 0;
      return { dx: dx + jitter, dy: dy - jitter, v: (shade * 0.22 + rim * 0.3) * flicker + limb, color: limb ? 2 : 3 };
    }
  }
}


const { BLINK_MS, BLINK_GAP_MS, STARTLE_MS, STARTLE_SCALE, LEAN_SCALE, RATE_EASE } = GAZE_PERSONALITY;

/** 0..1 compression of the dots over a double blink that began `age` ms ago. */
export function blinkAmount(age: number): number {
  if (age < 0) return 0;
  const second = BLINK_MS + BLINK_GAP_MS;
  const phase = age < BLINK_MS ? age : age >= second && age < second + BLINK_MS ? age - second : -1;
  return phase < 0 ? 0 : Math.sin((phase / BLINK_MS) * Math.PI);
}

function centerOf(target: Element | Point): Point {
  if ("getBoundingClientRect" in target) {
    const r = target.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }
  return target;
}

interface GazeLive {
  pointer: Point | null;
  pointerAt: number;
  speed: number;
  pointerType: PointerKind;
  focus: Point | null;
  focusAt: number;
  glance: Point | null;
  glanceAt: number;
  rand: number;
  lastSample: { x: number; y: number; t: number } | null;
}

/**
 * Dot-matrix sphere: denser and brighter toward the lit core, nine states. Every dot keeps its
 * place on the grid and springs toward where the current state wants it, so a state change is one
 * continuous morph that reaches the rim a beat after the core. Never a cut, never a crossfade.
 */
export const Orb = forwardRef<PresenceHandle, Props>(function Orb({ state, size, colors, reducedMotion, rings = 1, leanTo, label }, handle) {
  const ref = useRef<HTMLCanvasElement>(null);
  const dotsRef = useRef<Dot[] | null>(null);
  const leanToRef = useRef(leanTo);
  const st = useRef<{ state: OrbState; since: number }>({ state, since: 0 });
  const ringsRef = useRef(rings);
  const colorsRef = useRef(colors);
  useEffect(() => {
    colorsRef.current = colors;
    ringsRef.current = rings;
    leanToRef.current = leanTo;
  }, [colors, rings, leanTo]);
  useEffect(() => {
    if (st.current.state !== state) st.current = { state, since: performance.now() };
  }, [state]);
  const staticState = reducedMotion ? state : null;
  const gazeState = useRef<GazeState | null>(null);
  const gazeLive = useRef<GazeLive>({ pointer: null, pointerAt: 0, speed: 0, pointerType: "mouse", focus: null, focusAt: 0, glance: null, glanceAt: 0, rand: 0, lastSample: null });
  useImperativeHandle(
    handle,
    () => ({
      glance: (target) => {
        const g = gazeLive.current;
        g.glance = centerOf(target);
        g.glanceAt = performance.now();
        g.rand = Math.random();
      },
    }),
    [],
  );

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const pitch = size / N;
    const full = pitch * (N + PAD * 2);
    canvas.width = full * dpr;
    canvas.height = full * dpr;
    ctx.scale(dpr, dpr);
    const center = full / 2;
    const R = size / 2;

    const mainLab = toLab(hexToRgb(colorsRef.current.main));
    // The dots live across size and register changes, so a resize never restarts them from dark.
    if (!dotsRef.current) {
      const made: Dot[] = [];
      for (let j = 0; j < N; j++) {
        for (let i = 0; i < N; i++) {
          const x = (i + 0.5 - N / 2) / (N / 2);
          const y = (j + 0.5 - N / 2) / (N / 2);
          const r = Math.hypot(x, y);
          if (r > 1) continue;
          const seed = ((i * 73856093) ^ (j * 19349663)) % 1000 / 1000;
          made.push({ x, y, r, ang: Math.atan2(y, x), z: Math.sqrt(1 - r * r), seed, col: i, dx: 0, dy: 0, vx: 0, vy: 0, v: 0, vv: 0, lab: [...mainLab] as Lab, lastColor: 0, following: st.current.state, switchAt: 0 });
        }
      }
      dotsRef.current = made;
    }
    const dots = dotsRef.current;

    // Gaze input goes into a ref the frame loop reads; no React state per event.
    let teardownGaze = () => {};
    if (!reducedMotion) {
      const g = gazeLive.current;
      const onPointer = (e: PointerEvent) => {
        const kind: PointerKind = e.pointerType === "touch" ? "touch" : e.pointerType === "pen" ? "pen" : "mouse";
        // A finger drag is a scroll, not attention: touch counts only on contact.
        if (kind === "touch" && e.type !== "pointerdown") return;
        const now = performance.now();
        const prev = g.lastSample;
        g.speed = prev && now > prev.t ? (Math.hypot(e.clientX - prev.x, e.clientY - prev.y) / (now - prev.t)) * 1000 : 0;
        g.lastSample = { x: e.clientX, y: e.clientY, t: now };
        g.pointer = { x: e.clientX, y: e.clientY };
        g.pointerType = kind;
        g.pointerAt = now;
        g.rand = Math.random();
      };
      const onFocus = (e: FocusEvent) => {
        if (!(e.target instanceof Element) || e.target === canvas) return;
        g.focus = centerOf(e.target);
        g.focusAt = performance.now();
        g.rand = Math.random();
      };
      window.addEventListener("pointermove", onPointer, { passive: true });
      window.addEventListener("pointerdown", onPointer, { passive: true });
      window.addEventListener("focusin", onFocus);
      teardownGaze = () => {
        window.removeEventListener("pointermove", onPointer);
        window.removeEventListener("pointerdown", onPointer);
        window.removeEventListener("focusin", onFocus);
      };
    }
    gazeState.current = null;
    const spring = { x: 0, y: 0, vx: 0, vy: 0 };
    const eased = { brightness: 0, rate: 1 };
    let gazeClock = 0;
    let blinkAt = -Infinity;
    let startleAt = -Infinity;
    let rect = { at: -Infinity, cx: 0, cy: 0 };

    const t0 = performance.now();
    let raf = 0;
    let last = t0;
    let ringMix = 0;
    let visible = true;
    const lean: Lean = { x: 0, y: 0 };
    const leanGoal: Lean = { x: 0, y: 0 };
    let leanAt = 0;
    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      if (visible && !raf) raf = requestAnimationFrame(frame);
    });
    io.observe(canvas);

    function frame(now: number) {
      raf = 0;
      const c = colorsRef.current;
      const palette: RGB[] = [hexToRgb(c.main), hexToRgb(c.cream), hexToRgb(c.coral), hexToRgb(c.dim)];
      const paletteLab = palette.map(toLab);
      const cur = st.current;
      const age = reducedMotion ? 3 : (now - cur.since) / 1000;
      const dt = reducedMotion ? 1 : Math.min(0.05, (now - last) / 1000);
      last = now;

      // Curious-pet gaze: idle only, off under reduced motion.
      let gazeLean: Point = { x: 0, y: 0 };
      let startleEnv = 0;
      let blink = 0;
      if (!reducedMotion) {
        if (now - rect.at > 120) {
          const b = canvas!.getBoundingClientRect();
          rect = { at: now, cx: b.left + b.width / 2, cy: b.top + b.height / 2 };
        }
        if (!gazeState.current) gazeState.current = initialGaze(now);
        const live = gazeLive.current;
        const gin: GazeInput = {
          idle: cur.state === "idle",
          pointer: live.pointer,
          pointerAt: live.pointerAt,
          speed: live.speed,
          pointerType: live.pointerType,
          focus: live.focus,
          focusAt: live.focusAt,
          glance: live.glance,
          glanceAt: live.glanceAt,
          orbCenter: { x: rect.cx, y: rect.cy },
          orbRadius: R,
          rand: live.rand,
        };
        const res = nextGaze(gazeState.current, gin, now);
        if (res.state.phase !== gazeState.current.phase) canvas!.dataset.gaze = res.state.phase;
        gazeState.current = res.state;
        if (res.out.blink) blinkAt = now;
        if (res.out.startle) startleAt = now;
        const sx = stepSpring(spring.x, spring.vx, res.out.offset.x, dt);
        const sy = stepSpring(spring.y, spring.vy, res.out.offset.y, dt);
        spring.x = sx.pos;
        spring.vx = sx.vel;
        spring.y = sy.pos;
        spring.vy = sy.vel;
        const k = Math.min(1, RATE_EASE * dt);
        eased.brightness += (res.out.brightness - eased.brightness) * k;
        eased.rate += (res.out.breathRate - eased.rate) * k;
        gazeLean = res.out.lean;
        blink = blinkAmount(now - blinkAt);
        startleEnv = Math.exp(-(now - startleAt) / (STARTLE_MS / 2.2));
        if (startleEnv < 0.02) startleEnv = 0;
      }
      gazeClock += dt * eased.rate;
      const t = reducedMotion ? 1.3 : gazeClock;
      const damp = 2 * Math.sqrt(K);
      const tAbs = now / 1000;
      ctx!.clearRect(0, 0, full, full);

      // Where to lean: measured four times a second, eased, and released when attention ends.
      let wantLean: Lean = { x: 0, y: 0 };
      const leanToSel = leanToRef.current;
      if (cur.state === "attention" && leanToSel) {
        if (now - leanAt > 250) {
          leanAt = now;
          const me = canvas!.getBoundingClientRect();
          const target = document.querySelector(leanToSel)?.getBoundingClientRect();
          if (target) {
            const vx = target.left + target.width / 2 - (me.left + me.width / 2);
            const vy = target.top + target.height / 2 - (me.top + me.height / 2);
            const len = Math.hypot(vx, vy) || 1;
            leanGoal.x = vx / len;
            leanGoal.y = vy / len;
          }
        }
        wantLean = leanGoal;
      }
      lean.x += (wantLean.x - lean.x) * Math.min(1, 2.5 * dt);
      lean.y += (wantLean.y - lean.y) * Math.min(1, 2.5 * dt);

      // A key light that sits in front and only drifts a hair, so the highlight is the eye at the core and moves with it.
      const lx = Math.cos(t * 0.35) * 0.1;
      const ly = Math.sin(t * 0.28) * 0.08;
      const ll = Math.hypot(lx, ly, 1);
      const L = [lx / ll, ly / ll, 1 / ll];

      for (const d of dots) {
        if (d.following !== cur.state) {
          if (d.switchAt < cur.since) d.switchAt = cur.since + staggerDelay(d.r, d.seed);
          if (now >= d.switchAt) d.following = cur.state;
        }
        let shade = Math.max(0, d.x * L[0] + d.y * L[1] + d.z * L[2]);
        shade = Math.pow(shade, 2.2);
        const rim = Math.pow(1 - d.z, 4) * 0.5;
        const want = program(reducedMotion ? (cur.state === "attention" ? "attention" : "idle") : d.following, d, shade, rim, t, reducedMotion ? 3 : age, reducedMotion ? 0.1 : tAbs, lean);
        const targetLab = want.g != null ? toneAt(want.g) : paletteLab[want.color];
        if (reducedMotion) {
          d.dx = 0;
          d.dy = 0;
          d.v = want.v;
          d.lab = targetLab;
        } else {
          d.vx += ((want.dx - d.dx) * K - d.vx * damp) * dt;
          d.vy += ((want.dy - d.dy) * K - d.vy * damp) * dt;
          d.dx += d.vx * dt;
          d.dy += d.vy * dt;
          d.vv += ((want.v - d.v) * K * 1.2 - d.vv * damp * 1.1) * dt;
          d.v += d.vv * dt;
          // Coral drains back slowly; every other colour change is quick. Mixed in oklab.
          const m = Math.min(1, (d.lastColor === 2 && want.color !== 2 ? 1.6 : 7) * dt);
          d.lab = [d.lab[0] + (targetLab[0] - d.lab[0]) * m, d.lab[1] + (targetLab[1] - d.lab[1]) * m, d.lab[2] + (targetLab[2] - d.lab[2]) * m];
          if (Math.abs(targetLab[0] - d.lab[0]) < 0.02 && Math.abs(targetLab[1] - d.lab[1]) < 0.02) d.lastColor = want.g != null ? 0 : want.color;
        }
        const v = Math.max(0, d.v) * (1 + eased.brightness);
        if (v <= 0.02) continue;
        // Parallax: the dense core shifts more than the limb, so the outline stays round.
        const depth = 1 - d.r;
        let gx = d.x + d.dx + depth * spring.x;
        let gy = d.y + d.dy + depth * spring.y;
        const along = gx * gazeLean.x + gy * gazeLean.y;
        gx += gazeLean.x * along * LEAN_SCALE;
        gy += gazeLean.y * along * LEAN_SCALE;
        const grow = 1 + STARTLE_SCALE * startleEnv;
        const px = center + gx * grow * R;
        const py = center + gy * grow * R;
        const rad = pitch * 0.5 * (0.16 + 0.8 * Math.min(1, v)) * (1 - 0.55 * blink) * (1 + 0.2 * startleEnv);
        ctx!.globalAlpha = Math.min(1, 0.1 + v);
        const rgb = toRgb(d.lab);
        ctx!.fillStyle = `rgb(${rgb[0] | 0} ${rgb[1] | 0} ${rgb[2] | 0})`;
        ctx!.beginPath();
        ctx!.arc(px, py, rad, 0, Math.PI * 2);
        ctx!.fill();
      }

      // Orbit rings while acting: one faint tilted ring per running goal or workflow, eased in and out.
      const wantRings = cur.state === "acting" && !reducedMotion ? 1 : 0;
      ringMix += (wantRings - ringMix) * Math.min(1, 3 * dt);
      if (ringMix > 0.01) {
        const n = Math.min(3, Math.max(1, ringsRef.current));
        for (let k = 0; k < n; k++) {
          const tone = hexToRgb(TONES[k % 3]);
          ctx!.fillStyle = `rgb(${tone[0]} ${tone[1]} ${tone[2]})`;
          const tilt = -0.35 + k * 0.6;
          const rr = R * (1.22 + k * 0.08) * (0.7 + 0.3 * ringMix);
          const speed = (k % 2 ? -1 : 1) * (0.9 + k * 0.25);
          for (let q = 0; q < 48; q++) {
            const a = (q / 48) * Math.PI * 2 + t * speed;
            const ox = Math.cos(a) * rr;
            const oy = Math.sin(a) * rr * 0.22;
            const px = center + ox * Math.cos(tilt) - oy * Math.sin(tilt);
            const py = center + ox * Math.sin(tilt) + oy * Math.cos(tilt);
            const front = Math.sin(a) > 0;
            ctx!.globalAlpha = ringMix * (front ? 0.28 : 0.09);
            ctx!.beginPath();
            ctx!.arc(px, py, pitch * 0.13, 0, Math.PI * 2);
            ctx!.fill();
          }
        }
      }
      ctx!.globalAlpha = 1;
      if (!reducedMotion && visible && !document.hidden) raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    const onVis = () => {
      if (!document.hidden && !raf) raf = requestAnimationFrame(frame);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      teardownGaze();
      delete canvas.dataset.gaze;
      cancelAnimationFrame(raf);
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
    // Under reduced motion the loop draws one still frame, so a state change re-runs this effect.
  }, [size, reducedMotion, staticState]);

  const full = size + (size / N) * PAD * 2;
  return (
    <canvas
      ref={ref}
      role="img"
      aria-label={label ?? `Ze is ${state}`}
      style={{ width: full, height: full, margin: -(full - size) / 2, display: "block" }}
    />
  );
});
