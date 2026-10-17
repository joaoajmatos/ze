import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useLoopTransitionMutation } from "@/entities/loop";
import { Card } from "../hud/Cards";
import { DotMatrix } from "../hud/DotMatrix";
import { Corners } from "../hud/Frame";
import { Presence } from "../hud/Presence";
import { useJarvis } from "../JarvisShell";
import { compose, PRESETS, type Component } from "../model/compose";
import { useWorld } from "../model/world";

type Phase = "ready" | "listening" | "thinking" | "speaking" | "done";

const STEP = 80;
const DEFAULT_Q = PRESETS[0].q;
const EASE = [0.16, 1, 0.3, 1] as const;

/** Assemble: Ze picks the components a question needs and lays them out on the canvas, launched from its presence module. */
export function AssembleView() {
  const world = useWorld();
  const { orb, setOrb, colors, reducedMotion, narrow } = useJarvis();
  const [params] = useSearchParams();
  const [phase, setPhase] = useState<Phase>("ready");
  const [query, setQuery] = useState(params.get("q") ?? DEFAULT_Q);
  const [asked, setAsked] = useState(params.get("q") ?? DEFAULT_Q);
  const [run, setRun] = useState(0);
  const [queued, setQueued] = useState<null | "draft" | "later">(null);
  const [pinned, setPinned] = useState<Component[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const timers = useRef<number[]>([]);
  const started = useRef(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [launch, setLaunch] = useState<{ orb: DOMRect; cv: DOMRect } | null>(null);
  /** Measures the orb and the viewport right before the answer assembles, so cells fly in from the orb. */
  function measureLaunch() {
    const orb = document.querySelector(".presence-orb")?.getBoundingClientRect();
    const cv = document.querySelector(".assemble-main .hero")?.getBoundingClientRect();
    setLaunch(orb && cv ? { orb, cv } : null);
  }
  function launchOffset(i: number): { x: number; y: number } {
    if (narrow) return { x: 0, y: -40 };
    if (!launch) return { x: -260, y: -60 };
    const { orb, cv } = launch;
    let col = 0;
    let row = 0;
    let cx = 0;
    for (let j = 0; j <= i; j++) {
      const span = components[j]?.span ?? 12;
      if (col + span > 12) {
        col = 0;
        row += 1;
      }
      cx = cv.left + ((col + span / 2) / 12) * cv.width;
      col += span;
    }
    const cy = cv.top + 150 + row * 230 + 110;
    return { x: (orb.left + orb.width / 2 - cx) * 0.7, y: (orb.top + orb.height / 2 - cy) * 0.7 };
  }
  const transition = useLoopTransitionMutation();

  const composition = useMemo(() => compose(asked, world), [asked, world]);
  // The slip timeline is a desktop instrument; phones get the cards, which carry the same days.
  const components = [...pinned, ...composition.components.filter((c) => !dismissed.has(`${run}:${c.id}`) && !pinned.some((p) => p.id === c.id) && !(narrow && c.kind === "timeline"))];

  function clear() {
    for (const t of timers.current) window.clearTimeout(t);
    timers.current = [];
  }
  function finish() {
    clear();
    setPhase("done");
    setOrb("done");
    timers.current.push(window.setTimeout(() => setOrb("idle"), reducedMotion ? 0 : 1400));
    if (narrow) canvasRef.current?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  }
  function start(q: string) {
    clear();
    setAsked(q);
    setQueued(null);
    setRun((n) => n + 1);
    const k = reducedMotion ? 0 : 1;
    setPhase("listening");
    setOrb("listening");
    timers.current.push(window.setTimeout(() => (setPhase("thinking"), setOrb("thinking")), 650 * k + 1));
    timers.current.push(window.setTimeout(() => (measureLaunch(), setPhase("speaking"), setOrb("assembling")), 1400 * k + 2));
    timers.current.push(window.setTimeout(() => setOrb("speaking"), 1400 * k + 2 + 1200 * k));
    timers.current.push(window.setTimeout(finish, 1400 * k + 2 + 2600 * k));
  }
  useEffect(() => {
    if (!world.loading && !started.current) {
      started.current = true;
      start(query);
    }
    return clear;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [world.loading]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && phase !== "done" && phase !== "ready") finish();
      const target = e.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT");
      if (!typing && !e.metaKey && !e.ctrlKey && !e.altKey && /^[1-3]$/.test(e.key) && !world.loading) {
        const p = PRESETS[Number(e.key) - 1];
        if (p) {
          setQuery(p.q);
          start(p.q);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const busy = phase === "listening" || phase === "thinking" || phase === "speaking";
  const reply = phase === "done" || phase === "speaking";

  const tools = (c: Component) => {
    const isPinned = pinned.some((p) => p.id === c.id);
    return (
      <span className="tools">
        <button
          type="button"
          className="tool"
          aria-pressed={isPinned}
          aria-label={isPinned ? "Unpin: let the next question replace this" : "Pin: keep this across questions"}
          onClick={() => setPinned((ps) => (isPinned ? ps.filter((p) => p.id !== c.id) : [...ps, c]))}
        >
          {isPinned ? "pinned" : "pin"}
        </button>
        <button
          type="button"
          className="tool"
          aria-label="Dismiss this component"
          onClick={() => {
            setPinned((ps) => ps.filter((p) => p.id !== c.id));
            setDismissed((d) => new Set(d).add(`${run}:${c.id}`));
          }}
        >
          ×
        </button>
      </span>
    );
  };

  return (
    <main className="main assemble-main">
      <aside className="rail" aria-label="Ze's presence">
        <Presence state={orb} world={world} colors={colors} reducedMotion={reducedMotion} compact={narrow} />
        <nav className="presets" aria-label="Questions to try">
          <span className="lbl">try · keys 1–3</span>
          {PRESETS.map((p, i) => (
            <button key={p.q} type="button" className="ctl cmd" aria-pressed={asked === p.q} aria-keyshortcuts={String(i + 1)} onClick={() => (setQuery(p.q), start(p.q))} disabled={world.loading}>
              <span className="cmd-i">{String(i + 1).padStart(2, "0")}</span>
              <span className="cmd-q">{p.q}</span>
              <span className="cmd-k" aria-hidden="true">
                {i + 1}
              </span>
            </button>
          ))}
        </nav>
      </aside>
      <section className="hero canvas-hero" aria-label="Assembling answer" aria-busy={busy}>
        <Corners />
        <div className="hero-head">
          <span className="lbl on">Assemble · {phase === "ready" ? "ready" : phase === "done" ? "answered" : phase === "thinking" ? "reading the world-state" : phase}</span>
          <span className="lbl">
            {busy ? (
              <button type="button" className="ctl" onClick={finish}>
                Skip · Esc
              </button>
            ) : (
              `${components.length} components · ${pinned.length} pinned`
            )}
          </span>
        </div>
        <div className="hero-body" style={{ alignContent: "start", padding: "8px 0 0" }}>
          <div style={{ display: "grid", justifyItems: "center", gap: 12, width: "100%" }}>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                start(query);
              }}
              style={{ width: "min(100%, 640px)", padding: "0 18px" }}
            >
              <div className="ask">
                <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Ask Ze" />
                <button type="submit" className="ctl primary" disabled={world.loading}>
                  {phase === "ready" ? "Ask" : "Ask again"}
                </button>
              </div>
            </form>
            {reply && (
              <div className="stage-head" key={`h${run}`}>
                <motion.div initial={reducedMotion ? { opacity: 0 } : { opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, ease: EASE }}>
                  <DotMatrix text={composition.headline} size={narrow ? 2.6 : 4} title={composition.headline} />
                </motion.div>
                {composition.kind === "unknown" && <span className="lbl">I read that as “what's slipping?”</span>}
              </div>
            )}
            {reply && (
              <div className="canvas" ref={canvasRef}>
                <AnimatePresence>
                  {components.map((c, i) => (
                    <motion.div
                      key={c.id}
                      layout="position"
                      className={`cell span-${c.span}`}
                      initial={reducedMotion ? { opacity: 0 } : { opacity: 0, ...launchOffset(i), scale: 0.72, filter: narrow ? "blur(0px)" : "blur(6px)" }}
                      animate={{ opacity: 1, x: 0, y: 0, scale: 1, filter: "blur(0px)" }}
                      exit={reducedMotion ? { opacity: 0, transition: { duration: 0.01 } } : { opacity: 0, scale: 0.96, transition: { duration: 0.18, ease: EASE } }}
                      transition={reducedMotion ? { duration: 0.01 } : { duration: 0.62, ease: EASE, delay: pinned.some((p) => p.id === c.id) ? 0 : (i * STEP) / 1000, layout: { duration: 0.35, ease: EASE } }}
                    >
                      <Card
                        c={c}
                        world={world}
                        index={i}
                        delay={i * STEP}
                        reducedMotion={reducedMotion}
                        tools={tools(c)}
                        onTrack={(loopId, kind) => transition.mutate({ loopId, kind })}
                        busyLoop={transition.isPending ? (transition.variables?.loopId ?? null) : null}
                        onOffer={setQueued}
                        queued={queued}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
            {reply && components.length === 0 && (
              <p className="muted" style={{ padding: 18 }}>
                You dismissed everything. <button type="button" className="ctl" onClick={() => start(asked)}>Ask again</button>
              </p>
            )}
            {(phase === "listening" || phase === "thinking") && (
              <p className="lbl on" style={{ padding: "0 18px 18px" }}>
                {phase === "listening" ? "listening" : "reading the world-state"}
              </p>
            )}
            {transition.isError && <p className="hot" role="alert">That didn't go through. Try again.</p>}
          </div>
        </div>
        <div className="hero-foot">
          <Link to="/jarvis" className="ctl cmd">
            <span className="cmd-i">←</span>
            <span className="cmd-q">Back to the world</span>
          </Link>
        </div>
      </section>
    </main>
  );
}
