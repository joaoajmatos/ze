import { useEffect, useState } from "react";
import type { OrbState } from "../model/hud";
import type { World } from "../model/world";
import { DotMatrix } from "./DotMatrix";
import { Corners } from "./Frame";
import { Orb } from "./Orb";

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

export function statePhrase(state: OrbState, world: World): string {
  const running = world.goals.filter((g) => g.status !== "completed").length;
  const slipped = world.concerns.filter((c) => c.state === "drifting").length;
  switch (state) {
    case "idle":
      return slipped ? `${slipped} slipping · watching ${world.concerns.length}` : `watching ${world.concerns.length} concerns`;
    case "listening":
      return "listening";
    case "thinking":
      return "composing";
    case "speaking":
      return "speaking";
    case "assembling":
      return "assembling the answer";
    case "attention":
      return slipped ? `${slipped} promise${slipped > 1 ? "s" : ""} slipping` : "something needs you";
    case "acting":
      return running ? `acting on ${running} goal${running > 1 ? "s" : ""}` : "running a workflow";
    case "done":
      return "done";
    case "error":
      return "offline";
  }
}

/** Ze's presence, in its own framed module: status, session clock, the orb, its voice feed, and what it is doing. */
export function Presence({
  leanTo,
  state,
  world,
  colors,
  reducedMotion,
  compact = false,
}: {
  state: OrbState;
  world: World;
  colors: { main: string; cream: string; coral: string; dim: string };
  reducedMotion: boolean;
  compact?: boolean;
  leanTo?: string;
}) {
  const clock = useSessionClock();
  const online = state !== "error";
  const orbSize = compact ? 150 : 184;
  const rings = Math.max(1, world.goals.filter((g) => g.status !== "completed").length + world.workflows.filter((w) => w.enabled).length);
  return (
    <section className={`mod presence ${state === "attention" ? "hot" : ""}`} aria-label="Ze's presence">
      <Corners />
      <header className="presence-head">
        <span className={`lbl ${online ? "on" : "hot"}`} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <i className={`pulse ${online ? "" : "off"}`} aria-hidden="true" /> {online ? "Online" : "Offline"}
        </span>
        <DotMatrix text={clock} size={2.4} title={`Session ${clock}`} />
      </header>
      <div className="presence-orb">
        <Orb state={state} size={orbSize} colors={colors} reducedMotion={reducedMotion} rings={rings} leanTo={leanTo} />
      </div>
      <footer className="presence-foot">
        <span className="lbl">presence</span>
        <span className={`t ${state === "attention" ? "hot" : ""}`} aria-live={state === "attention" || state === "done" || state === "error" ? "polite" : "off"}>
          {statePhrase(state, world)}
        </span>
      </footer>
    </section>
  );
}
