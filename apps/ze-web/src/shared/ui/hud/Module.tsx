import { useRef, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import { ChatAboutChip } from "./ChatAboutChip";
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
  /** Adds the "Chat about this" chip and the `c` key; called with the module's element. */
  onChatAbout?: (element: Element) => void;
  /** What the chat is about, for the chip's accessible name. Defaults to the module label. */
  chatAboutLabel?: string;
}

export function Module({ label, index, tone = "default", children, className = "", style, as = "section", headless = false, tools, onChatAbout, chatAboutLabel }: ModuleProps) {
  const Tag = as;
  const root = useRef<HTMLElement>(null);
  const onKeyDown = onChatAbout
    ? (e: KeyboardEvent<HTMLElement>) => {
        if (e.key !== "c" || e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented) return;
        const target = e.target instanceof HTMLElement ? e.target : null;
        if (target && (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable)) return;
        e.preventDefault();
        if (root.current) onChatAbout(root.current);
      }
    : undefined;
  return (
    <Tag ref={root as never} onKeyDown={onKeyDown} className={`mod ${tone === "hot" ? "hot" : tone === "dotted" ? "dotted" : tone === "cream" ? "cream" : ""} ${headless ? "headless" : ""} ${tools ? "has-tools" : ""} ${className}`} style={style} aria-label={label} role={as === "div" ? "group" : undefined}>
      <Corners />
      <header className="mod-head">
        <h2 className={`lbl ${tone === "hot" ? "hot" : tone === "cream" ? "ink" : ""}`}>{label}</h2>
        <span className="mod-right">
          {onChatAbout && <ChatAboutChip label={chatAboutLabel ?? label} onClick={() => root.current && onChatAbout(root.current)} />}
          {index && <span className="idx">{index}</span>}
          {tools}
        </span>
      </header>
      {children}
    </Tag>
  );
}
