import type { CSSProperties, ReactNode } from "react";
import { Corners } from "./Corners";

interface ModuleProps {
  label: string;
  /** Instrument id; only the Assemble canvas passes it (DESIGN.md). */
  index?: string;
  tone?: "default" | "hot" | "dotted" | "cream";
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
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
