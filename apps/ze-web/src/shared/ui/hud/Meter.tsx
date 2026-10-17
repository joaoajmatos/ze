import type { CSSProperties } from "react";

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
      style={{ "--d": `${delay}ms` } as CSSProperties}
    >
      {Array.from({ length: ticks }, (_, i) => (
        <i key={i} className={i < lit ? "lit" : ""} style={{ "--i": i } as CSSProperties} />
      ))}
    </span>
  );
}
