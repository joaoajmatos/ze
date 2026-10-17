import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { DotMatrix } from "./hud/DotMatrix";
import { useAmbience } from "./hud/useAmbience";
import { dayMonth, hhmm, longDate, weekday } from "./model/format";
import { ORB_STATES, PALETTES, type OrbState, type PaletteId } from "./model/hud";

interface Ctx {
  palette: PaletteId;
  orb: OrbState;
  setOrb: (s: OrbState) => void;
  reducedMotion: boolean;
  /** Phone-width layout. */
  narrow: boolean;
  colors: { main: string; cream: string; coral: string; dim: string };
}

const JarvisCtx = createContext<Ctx | null>(null);
export function useJarvis(): Ctx {
  const c = useContext(JarvisCtx);
  if (!c) throw new Error("useJarvis outside JarvisShell");
  return c;
}

const PALETTE_COLORS: Record<PaletteId, Ctx["colors"]> = {
  ultraviolet: { main: "#9e82ff", cream: "#f2eadb", coral: "#ff6e5a", dim: "#8f88ad" },
  amethyst: { main: "#c08cff", cream: "#f4eee3", coral: "#ff7a60", dim: "#9391b0" },
  orchid: { main: "#b9a3ff", cream: "#efe5d7", coral: "#ff6f63", dim: "#9a90ae" },
};

function useReducedMotion(): boolean {
  const [rm, setRm] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setRm(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return rm;
}

function useNarrow(): boolean {
  const [n, setN] = useState(() => window.matchMedia?.("(max-width: 1023px)").matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    const on = () => setN(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return n;
}

function useClock(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 15_000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

/** Prototype-only controls: a secondary cluster on desktop, a closed disclosure on phones. */
function ProtoGroup({ narrow, children }: { narrow: boolean; children: ReactNode }) {
  if (!narrow) {
    return (
      <div className="proto" role="group" aria-label="Prototype controls">
        {children}
      </div>
    );
  }
  return (
    <details className="proto-disclosure">
      <summary className="ctl" aria-label="Prototype controls: palette, orb state, ambience">
        Proto
      </summary>
      <div className="proto" role="group" aria-label="Prototype controls">
        {children}
      </div>
    </details>
  );
}

export function JarvisShell({ children, showAsk = true }: { children: ReactNode; showAsk?: boolean }) {
  const [palette, setPalette] = useState<PaletteId>(() => (localStorage.getItem("jarvis.palette.v2") as PaletteId) || "orchid");
  const [orb, setOrb] = useState<OrbState>("idle");
  const reducedMotion = useReducedMotion();
  const narrow = useNarrow();
  const ambience = useAmbience();
  const now = useClock();
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  useEffect(() => {
    localStorage.setItem("jarvis.palette.v2", palette);
  }, [palette]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        const el = document.querySelector<HTMLInputElement>('input[aria-label="Ask Ze"]');
        if (el) {
          e.preventDefault();
          el.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const ctx = useMemo<Ctx>(
    () => ({ palette, orb, setOrb, reducedMotion, narrow, colors: PALETTE_COLORS[palette] }),
    [palette, orb, reducedMotion, narrow],
  );


  return (
    <JarvisCtx.Provider value={ctx}>
      <div className="jarvis" data-palette={palette}>
        <div className="shell">
          <header className="top">
            <div className="brand">
              <DotMatrix text="ZE" size={3} color="var(--main)" title="Ze" />
              <span className="lbl">world-state</span>
            </div>
            <nav className="tabs" aria-label="Views">
              <NavLink to="/jarvis" end className="ctl">
                World
              </NavLink>
              <NavLink to="/jarvis/assemble" className="ctl">
                Assemble
              </NavLink>
            </nav>
            <ProtoGroup narrow={narrow}>
              <span className="lbl">proto</span>
            <div className="seg" role="group" aria-label="Palette">
              {PALETTES.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="ctl"
                  aria-pressed={palette === p.id}
                  onClick={() => setPalette(p.id)}
                  title={p.note}
                  aria-label={`${p.name} palette: ${p.note}`}
                  style={{ "--sw": PALETTE_COLORS[p.id].main } as React.CSSProperties}
                >
                  <i className="swatch" aria-hidden="true" />
                  <span className="sw-name">{p.name}</span>
                </button>
              ))}
            </div>
            <label className="ctl orb-ctl" title={ORB_STATES.find((o) => o.id === orb)?.note}>
              <span>Orb</span>
              <select value={orb} onChange={(e) => setOrb(e.target.value as OrbState)} aria-label="Orb state">
                {ORB_STATES.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.id}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="ctl" aria-pressed={ambience.on} onClick={ambience.toggle} aria-label={`Ambience ${ambience.on ? "on" : "off"}`}>
              Ambience
            </button>
            </ProtoGroup>
          </header>
          <div className="strip">
            <div className="coords" role="note" aria-label="Legend: solid means told, dotted means inferred or suspected, coral means slipping">
              <span className="lbl">claims · filled told · half inferred · dashed suspected</span>
              <span className="lbl hot">coral slipping</span>
            </div>
            <div className="clock" aria-label={`${longDate(now)}, ${hhmm(now)}`}>
              <span className="lbl only-wide">{longDate(now)}</span>
              <span className="lbl only-narrow">
                {weekday(now)} {dayMonth(now)}
              </span>
              <DotMatrix text={hhmm(now)} size={3} />
            </div>
          </div>
          {children}
          {showAsk && (
          <form
            className="bottom"
            onSubmit={(e) => {
              e.preventDefault();
              const text = q.trim() || "what's slipping?";
              navigate(`/jarvis/assemble?q=${encodeURIComponent(text)}`);
              setQ("");
            }}
          >
            <div className="ask">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Ask Ze — try: what's slipping?"
                aria-label="Ask Ze"
              />
              <button type="button" className="ctl" aria-label="Talk to Ze" onClick={() => setOrb(orb === "listening" ? "idle" : "listening")}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" aria-hidden="true">
                  <rect x="5.5" y="1.5" width="5" height="8" rx="2.5" />
                  <path d="M3 7.5a5 5 0 0 0 10 0M8 12.5v2" />
                </svg>
              </button>
              <button type="submit" className="ctl">
                Ask
              </button>
            </div>
          </form>
          )}
        </div>
      </div>
    </JarvisCtx.Provider>
  );
}
