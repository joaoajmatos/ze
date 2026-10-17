import { useEffect, useRef, useState, type ReactNode } from "react";

/** Claim-kind glyph, the same vocabulary as the field marks: filled told, half inferred, dashed suspected, hollow goal. */
export function Glyph({ kind, hot = false }: { kind: "told" | "inferred" | "suspected" | "goal"; hot?: boolean }) {
  return <i className={`glyph ${kind} ${hot ? "hot" : ""}`} aria-hidden="true" />;
}

/**
 * Confidence over time as a tiny line: from where it stood when last evidenced to where decay has
 * taken it now. A flat line means fresh evidence; a falling one means the claim is ageing.
 */
export function Spark({ from, to, hot = false, dotted = false, label }: { from: number | null; to: number | null; hot?: boolean; dotted?: boolean; label: string }) {
  const W = 46;
  const H = 14;
  const a = from ?? to ?? 0.5;
  const b = to ?? a;
  const pts: string[] = [];
  for (let i = 0; i <= 8; i++) {
    const k = i / 8;
    const v = a + (b - a) * (1 - Math.pow(1 - k, 2));
    pts.push(`${(k * (W - 2) + 1).toFixed(1)},${(H - 1 - v * (H - 2)).toFixed(1)}`);
  }
  return (
    <svg className={`spark ${hot ? "hot" : ""} ${dotted ? "dotted" : ""}`} width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line x1={1} x2={W - 1} y1={H - 1} y2={H - 1} className="spark-base" />
      <polyline points={pts.join(" ")} className="spark-line" />
      <circle cx={W - 1} cy={H - 1 - b * (H - 2)} r={1.8} className="spark-dot" />
    </svg>
  );
}

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

export function Corners() {
  return (
    <>
      <i className="corner tl" aria-hidden="true" />
      <i className="corner tr" aria-hidden="true" />
      <i className="corner bl" aria-hidden="true" />
      <i className="corner br" aria-hidden="true" />
    </>
  );
}

interface ModuleProps {
  label: string;
  index?: string;
  tone?: "default" | "hot" | "dotted" | "cream";
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  as?: "section" | "div" | "article";
  /** No header strip; the label stays as the accessible name only. */
  headless?: boolean;
  /** Controls in the header's right slot, such as pin and dismiss. */
  tools?: ReactNode;
}

export function Module({ label, index, tone = "default", children, className = "", style, as = "section", headless = false, tools }: ModuleProps) {
  const Tag = as;
  return (
    <Tag className={`mod ${tone === "hot" ? "hot" : tone === "dotted" ? "dotted" : tone === "cream" ? "cream" : ""} ${headless ? "headless" : ""} ${tools ? "has-tools" : ""} ${className}`} style={style} aria-label={label}>
      <Corners />
      <header className="mod-head">
        <h2 className={`lbl ${tone === "hot" ? "hot" : tone === "cream" ? "ink" : ""}`}>{label}</h2>
        <span className="mod-right">
          {index && <span className="idx">{index}</span>}
          {tools}
        </span>
      </header>
      {children}
    </Tag>
  );
}


/** Tick-bar meter. value 0..1; dotted for inferred/suspected, hot for slipped. */
export function Meter({
  value,
  ticks = 12,
  tone = "default",
  animate = false,
  delay = 0,
  label,
}: {
  value: number | null;
  ticks?: number;
  tone?: "default" | "hot" | "dotted";
  animate?: boolean;
  delay?: number;
  label?: string;
}) {
  const lit = value == null ? 0 : Math.round(value * ticks);
  return (
    <span
      className={`meter ${tone} ${animate ? "meter-in" : ""}`}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value == null ? undefined : Math.round(value * 100)}
      aria-valuetext={value == null ? "unknown" : `${Math.round(value * 100)} percent sure${tone === "hot" ? ", slipping" : tone === "dotted" ? ", inferred" : ""}`}
      aria-label={label ?? "confidence"}
      style={{ "--d": `${delay}ms` } as React.CSSProperties}
    >
      {Array.from({ length: ticks }, (_, i) => (
        <i key={i} className={i < lit ? "lit" : ""} style={{ "--i": i } as React.CSSProperties} />
      ))}
    </span>
  );
}

export function Dots({ max, lit, label }: { max: number; lit: number; label: string }) {
  return (
    <span className="dots" role="img" aria-label={label}>
      {Array.from({ length: max }, (_, i) => (
        <i key={i} className={i < lit ? "lit" : ""} />
      ))}
    </span>
  );
}

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
