import { useEffect, useRef } from "react";

/** Counts a numeral up during the cascade; renders the final value at once under reduced motion. */
export function CountUp({ to, delay = 0, duration = 650, reducedMotion }: { to: number; delay?: number; duration?: number; reducedMotion: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reducedMotion) {
      el.textContent = String(to);
      return;
    }
    let raf = 0;
    const t0 = performance.now() + delay;
    const tick = (now: number) => {
      const k = Math.min(1, Math.max(0, (now - t0) / duration));
      const eased = 1 - Math.pow(1 - k, 3);
      el.textContent = String(Math.round(eased * to));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, delay, duration, reducedMotion]);
  // Written through the ref each frame, so counting never re-renders React.
  return <span ref={ref}>{reducedMotion ? to : 0}</span>;
}
