import { forwardRef, useEffect, useState, type ReactNode } from "react";
import { useReducedMotion } from "@/shared/lib/use-reduced-motion";
import { Corners } from "../Corners";
import { DotMatrix } from "../DotMatrix";
import { Orb } from "./Orb";
import type { OrbState, PresenceHandle } from "./types";
import { usePaletteColors } from "./usePaletteColors";

function useSessionClock(): string {
  const [s, setS] = useState(0);
  useEffect(() => {
    const t0 = Date.now();
    const id = window.setInterval(() => setS(Math.floor((Date.now() - t0) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, []);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

const LIVE_STATES: readonly OrbState[] = ["attention", "done", "error"];

interface PresenceProps {
  state: OrbState;
  phrase: string;
  compact?: boolean;
  /** Running goals and workflows; one faint orbit ring each while acting. */
  rings?: number;
  /** CSS selector of the item the orb leans toward while in attention. */
  leanTo?: string;
  /** Rendered after the clock in the head: the shell puts the ambience toggle here. */
  headSlot?: ReactNode;
  /** Input level 0..1 for the orb while it listens. */
  level?: () => number;
}

/** Ze's presence in its own framed module: status, session clock, the orb and what it is doing. */
export const Presence = forwardRef<PresenceHandle, PresenceProps>(function Presence({ state, phrase, compact = false, rings, leanTo, headSlot, level }, handle) {
  const clock = useSessionClock();
  const colors = usePaletteColors();
  const reducedMotion = useReducedMotion();
  const online = state !== "error";
  return (
    <section className={`mod presence ${state === "attention" ? "hot" : ""}`} aria-label="Ze's presence">
      <Corners />
      <header className="presence-head">
        <span className={`lbl ${online ? "on" : "hot"}`} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <i className={`pulse ${online ? "" : "off"}`} aria-hidden="true" /> {online ? "Online" : "Offline"}
        </span>
        <DotMatrix text={clock} size={2.4} title={`Session ${clock}`} />
        {headSlot}
      </header>
      <div className="presence-orb">
        <Orb ref={handle} state={state} size={compact ? 150 : 184} colors={colors} reducedMotion={reducedMotion} rings={rings} leanTo={leanTo} level={level} />
      </div>
      <footer className="presence-foot">
        <span className="lbl">presence</span>
        <span className={`t ${state === "attention" ? "hot" : ""}`}>{phrase}</span>
        {/* The live region stays mounted so a screen reader hears its text change. */}
        <span className="sr-only" role="status" aria-live="polite">
          {LIVE_STATES.includes(state) ? phrase : ""}
        </span>
      </footer>
    </section>
  );
});
