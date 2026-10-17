import { useEffect, useState } from "react";

const GLYPHS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789·:-";

/** Text that decodes in, left to right, from scrambled glyphs; renders at once under reduced motion. */
export function Decode({ text, delay = 0, duration = 520, reducedMotion }: { text: string; delay?: number; duration?: number; reducedMotion: boolean }) {
  const [shown, setShown] = useState(reducedMotion ? text : "");
  useEffect(() => {
    if (reducedMotion) return;
    let raf = 0;
    const t0 = performance.now() + delay;
    const tick = (now: number) => {
      const k = Math.min(1, Math.max(0, (now - t0) / duration));
      const settled = Math.floor(k * text.length);
      let out = text.slice(0, settled);
      for (let i = settled; i < text.length; i++) {
        const ch = text[i];
        out += ch === " " ? " " : k === 1 ? ch : GLYPHS[(i * 7 + Math.floor(now / 40)) % GLYPHS.length];
      }
      setShown(out);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, delay, duration, reducedMotion]);
  return <span className="decode">{reducedMotion ? text : shown}</span>;
}
