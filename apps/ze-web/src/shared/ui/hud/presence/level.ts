const ATTACK = 0.5;
const RELEASE = 0.12;

/** One frame of level smoothing: quick to rise, slow to fall. Input and output are 0..1. */
export function smoothLevel(prev: number, raw: number): number {
  const target = Math.min(1, Math.max(0, raw));
  const k = target > prev ? ATTACK : RELEASE;
  return Math.min(1, Math.max(0, prev + (target - prev) * k));
}
