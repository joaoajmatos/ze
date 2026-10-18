import { useLayoutEffect, type RefObject } from "react";
import { presenceActions } from "@/entities/presence";
import { useReducedMotion } from "@/shared/lib";

const STEP_MS = 80;
const FLY_MS = 460;
const EASE = "cubic-bezier(0.16, 1, 0.3, 1)";

/**
 * A live reply's modules fly out of the orb, 80 ms apart, while the orb shows "assembling". Under reduced motion
 * they fade in place, same timing, no movement. Plays once: `onPlayed` clears the reply from the live set, so a remount does not replay it.
 */
export function useCascade(root: RefObject<HTMLElement | null>, live: boolean, onPlayed?: () => void) {
  const reduced = useReducedMotion();
  useLayoutEffect(() => {
    const el = root.current;
    if (!live || !el || typeof el.animate !== "function") return;
    const targets = [...el.querySelectorAll<HTMLElement>("[data-cascade]")];
    if (targets.length === 0) return;
    const orb = document.querySelector(".presence-orb")?.getBoundingClientRect();
    const animations: Animation[] = [];
    onPlayed?.();
    targets.forEach((target, i) => {
      const rect = target.getBoundingClientRect();
      const keyframes: Keyframe[] =
        reduced || !orb
          ? [{ opacity: 0 }, { opacity: 1 }]
          : [
              {
                opacity: 0,
                transform: `translate(${orb.left + orb.width / 2 - (rect.left + rect.width / 2)}px, ${orb.top + orb.height / 2 - (rect.top + rect.height / 2)}px) scale(0.2)`,
              },
              { opacity: 1, transform: "none" },
            ];
      animations.push(target.animate(keyframes, { duration: FLY_MS, delay: i * STEP_MS, easing: EASE, fill: "backwards" }));
    });
    presenceActions.setWorldSignal("assembling");
    const done = window.setTimeout(() => presenceActions.setWorldSignal(null), (targets.length - 1) * STEP_MS + FLY_MS);
    return () => {
      window.clearTimeout(done);
      presenceActions.setWorldSignal(null);
      animations.forEach((a) => a.cancel());
    };
    // The cascade belongs to the mount of this reply; later re-renders must not replay it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
