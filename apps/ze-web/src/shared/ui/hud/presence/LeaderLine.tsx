import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface Props {
  /** The orb canvas: the line starts at its coral core. */
  from: string;
  /** The square mark itself (the data point), never its label or group. */
  to: string;
  reducedMotion: boolean;
}

/**
 * A thin coral line of flowing dots from the orb's core to the slipping item's mark. It lives in a
 * body portal (one shared viewport space), is measured with getBoundingClientRect, and is updated
 * through refs inside rAF on scroll, resize and layout change, so scrolling never re-renders React.
 */
export function LeaderLine({ from, to, reducedMotion }: Props) {
  const base = useRef<SVGLineElement>(null);
  const flow = useRef<SVGLineElement>(null);
  const tip = useRef<SVGCircleElement>(null);
  const root = useRef<SVGSVGElement>(null);
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      raf = 0;
      const a = document.querySelector(from)?.getBoundingClientRect();
      const b = document.querySelector(to)?.getBoundingClientRect();
      const svg = root.current;
      if (!svg) return;
      if (!a || !b || b.width === 0) {
        svg.style.display = "none";
        return;
      }
      svg.style.display = "";
      const ax = a.left + a.width / 2;
      const ay = a.top + a.height / 2;
      const bx = b.left + b.width / 2;
      const by = b.top + b.height / 2;
      const len = Math.hypot(bx - ax, by - ay) || 1;
      const ux = (bx - ax) / len;
      const uy = (by - ay) / len;
      // Start inside the coral core and end exactly on the mark's centre.
      const x1 = ax + ux * a.width * 0.05;
      const y1 = ay + uy * a.width * 0.05;
      for (const el of [base.current, flow.current]) {
        el?.setAttribute("x1", String(x1));
        el?.setAttribute("y1", String(y1));
        el?.setAttribute("x2", String(bx));
        el?.setAttribute("y2", String(by));
      }
      tip.current?.setAttribute("cx", String(bx));
      tip.current?.setAttribute("cy", String(by));
      tip.current?.setAttribute("r", String(Math.max(4, b.width * 0.55)));
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(measure);
    };
    measure();
    const t = window.setTimeout(measure, 400);
    window.addEventListener("scroll", schedule, { capture: true, passive: true });
    window.addEventListener("resize", schedule);
    const ro = new ResizeObserver(schedule);
    ro.observe(document.body);
    const hero = document.querySelector(".hero");
    if (hero) ro.observe(hero);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(t);
      window.removeEventListener("scroll", schedule, true);
      window.removeEventListener("resize", schedule);
      ro.disconnect();
    };
  }, [from, to]);
  return createPortal(
    <svg ref={root} className={`leader ${reducedMotion ? "still" : ""}`} aria-hidden="true">
      <line ref={base} className="leader-base" />
      <line ref={flow} className="leader-flow" />
      <circle ref={tip} className="leader-tip" />
    </svg>,
    document.body,
  );
}
