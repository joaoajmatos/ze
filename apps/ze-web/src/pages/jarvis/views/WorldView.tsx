import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useLoopTransitionMutation } from "@/entities/loop";
import { FieldChart } from "../hud/FieldChart";
import { CountUp, Corners, Dots, Glyph, Meter, Module, Spark } from "../hud/Frame";
import { LeaderLine } from "../hud/LeaderLine";
import { Presence } from "../hud/Presence";
import { useJarvis } from "../JarvisShell";
import { ago, hhmm, pct, relDay, sourceLabel, staleness, stateLabel } from "../model/format";
import { daysSince, decisionsFor, kindLabelOf, postureOf, short, slipsOf, worldSentence } from "../model/hud";
import { useWorld } from "../model/world";

const ASK_SLIPPING = "/jarvis/assemble?q=what%27s%20slipping%3F";

/** The human line of a failure body: the step that failed and the tool, never a traceback fragment. */
function humanFailure(body: string): string {
  const step = body.match(/^(Step \d+ \([^)]*\)) failed/);
  const tool = body.match(/Tool (\w+) failed/);
  const timeout = body.match(/(\w+) timed out after ([\d.]+)s/);
  if (timeout) return `${timeout[1]} timed out after ${Math.round(Number(timeout[2]))} s.`;
  if (step && tool) return `${step[1]} failed: the ${tool[1]} tool errored.`;
  if (step) return `${step[1]} failed.`;
  const first = body.split(/[.:]\s/)[0];
  return first.length > 90 ? `${first.slice(0, 88)}…` : first;
}

export function WorldView() {
  const world = useWorld();
  const { orb, setOrb, colors, reducedMotion, narrow } = useJarvis();
  const [selected, setSelected] = useState<string | null>(null);
  const readoutRef = useRef<HTMLDivElement>(null);
  const transition = useLoopTransitionMutation();
  const sel = world.concerns.find((c) => c.id === selected) ?? null;
  const slips = slipsOf(world);
  const slipped = slips.filter((s) => s.kind === "slipped");
  const decisions = decisionsFor(world);
  const weekAgo = world.now.getTime() - 7 * 86400_000;
  const inflows = ["conversation", "email", "calendar", "ingestion"].map((k) => ({
    k,
    n: world.concerns.filter((c) => (c.sources.includes(k) || c.provenance === k) && (c.updatedAt ?? c.createdAt ?? world.now).getTime() >= weekAgo).length,
  }));
  const weekRuns = world.workflows.flatMap((w) => w.runs.filter((r) => r.at.getTime() >= weekAgo));
  const runsOk = weekRuns.filter((r) => r.ok).length;
  const runningGoal = world.goals.find((g) => g.status !== "completed");
  const nextWf = world.workflows
    .filter((w) => w.enabled && w.nextRun && w.nextRun >= world.now)
    .sort((a, b) => a.nextRun!.getTime() - b.nextRun!.getTime())[0];
  const loopsShown = world.concerns.filter((c) => c.kind === "loop" && c.state !== "suspected");
  const suspectedCount = world.concerns.filter((c) => c.state === "suspected").length;

  useEffect(() => {
    if (sel) readoutRef.current?.focus();
  }, [sel]);
  // The orb holds attention while something has slipped and drains back to idle once nothing has.
  const slippedCount = world.loading ? -1 : slipped.length;
  useEffect(() => {
    if (slippedCount < 0) return;
    setOrb(slippedCount ? "attention" : "idle");
  }, [slippedCount, setOrb]);
  const leaderOn = orb === "attention" && slipped.length > 0 && !narrow;
  // The mark's CSS pulse and the orb's heartbeat share one absolute clock (2.2 s period).
  useEffect(() => {
    if (orb === "attention") document.documentElement.style.setProperty("--beat-offset", `${-((performance.now() / 1000) % 2.2)}s`);
  }, [orb]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function select(id: string | null) {
    setSelected(id);
  }

  return (
    <main className="main">
      <aside className="rail" aria-label="Ze status">
        <Presence leanTo={narrow ? undefined : ".pt.hot rect"} state={orb} world={world} colors={colors} reducedMotion={reducedMotion} compact />


        <Module label="Needs you" index="A·02" tone={decisions.length ? "cream" : "default"} className="mod-needs">
          {decisions.length === 0 && <p className="muted">Nothing waiting on you.</p>}
          {decisions.map((d) => {
            const loopId = d.kind === "suspicion" ? d.id.replace(/^loop:/, "") : null;
            const busy = transition.isPending && transition.variables?.loopId === loopId;
            return (
              <div key={d.id} className={`row ${d.kind === "suspicion" ? "dotted" : ""}`}>
                {d.href ? (
                  <Link to={d.href} className="t">
                    {d.title}
                  </Link>
                ) : loopId ? (
                  <button type="button" className="t ctl-text" onClick={() => select(loopId)}>
                    {d.title}
                  </button>
                ) : (
                  <span className="t">{d.title}</span>
                )}
                <span className={`lbl ${d.kind === "gate" || d.kind === "held_write" ? "hot" : ""}`}>
                  {d.kind === "suspicion" ? "confirm?" : d.kind === "gate" ? "gate" : d.kind === "held_write" ? "approve" : "review"}
                </span>
                <span className="s">{d.detail.length > 90 ? `${d.detail.slice(0, 88)}…` : d.detail}</span>
                {loopId && (
                  <span className="acts">
                    <button type="button" className="ctl" disabled={busy} onClick={() => transition.mutate({ loopId, kind: "confirm" })}>
                      Yes, track it
                    </button>
                    <button type="button" className="ctl" disabled={busy} onClick={() => transition.mutate({ loopId, kind: "drop" })}>
                      Drop
                    </button>
                  </span>
                )}
              </div>
            );
          })}
          {transition.isError && <p className="hot" style={{ marginTop: 8, fontSize: "0.875rem" }} role="alert">That didn't go through. Try again.</p>}
        </Module>

        <Module label="Doing now" index="A·03">
          {runningGoal ? (
            <div className="row">
              <span className="t">{runningGoal.title}</span>
              <span className="ro on">
                {runningGoal.done}/{runningGoal.total}
              </span>
              <span className="s">{runningGoal.openGate ? "Milestones done · waiting on your OK" : stateLabel(runningGoal.status)}</span>
            </div>
          ) : (
            <div className="row">
              <span className="t muted">No goal running</span>
            </div>
          )}
          {nextWf ? (
            <div className="row">
              <span className="t">{nextWf.name}</span>
              <span className="ro">
                {relDay(nextWf.nextRun!, world.now)} {hhmm(nextWf.nextRun!)}
              </span>
              <span className="s">{nextWf.runs.length ? `${nextWf.runs.filter((r) => r.ok).length}/${nextWf.runs.length} recent runs ok` : "scheduled"}</span>
            </div>
          ) : (
            <div className="row">
              <span className="t muted">No workflow due this week</span>
            </div>
          )}
          <div className="row">
            <span className="t">Runs · 7 d</span>
            <span className={`lbl ${weekRuns.length - runsOk ? "hot" : ""}`}>
              {runsOk} ok · {weekRuns.length - runsOk} failed
            </span>
          </div>
        </Module>

        <Module label="Governance" index="A·04">
          <div className="row">
            <span className="t">Sync</span>
            <span className="ro on">{world.loading ? "syncing" : `synced ${hhmm(world.now)}`}</span>
          </div>
          <div className="row">
            <span className="t">Quiet hours</span>
            <span className="lbl">{world.budget.quietEnabled ? (world.budget.quietNow ? "holding" : "armed") : "off"}</span>
          </div>
          <div className="row">
            <span className="t">Push budget</span>
            <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
              <Dots max={world.budget.max} lit={world.budget.spent} label={`${world.budget.spent} of ${world.budget.max} pushes used today`} />
              <span className="ro">{world.budget.spent} of {world.budget.max} used</span>
            </span>
          </div>
          <div className="row">
            <span className="t">Held for you</span>
            {world.budget.held ? <span className="num md">{world.budget.held}</span> : <span className="lbl">none</span>}
          </div>
        </Module>
      </aside>

      <section className={`hero ${orb === "attention" ? "attn" : ""}`} aria-label="World-state viewport">
        {leaderOn && <LeaderLine from=".presence-orb canvas" to=".pt.hot rect" reducedMotion={reducedMotion} />}
        <Corners />
        <div className="hero-head">
          <span className="lbl on">
            {narrow ? `World · ${world.concerns.length}` : `Time left × how sure · ${world.concerns.length} concerns`}
          </span>
          <span className="lbl">
            {world.sourcesFailed.length ? (
              <span className="hot">{world.sourcesFailed.length} source{world.sourcesFailed.length > 1 ? "s" : ""} down: {world.sourcesFailed.join(", ")}</span>
            ) : slipped.length ? (
              <span className="hot">{slipped.length} slipping</span>
            ) : (
              "steady"
            )}
          </span>
        </div>
        <div className="hero-body">
          <FieldChart world={world} selected={sel?.id ?? null} onSelect={select} narrow={narrow} />
        </div>
        <p className="legend" aria-label="How to read the field">
          <span>
            <i className="mark filled" /> told · evidenced
          </span>
          <span>
            <i className="mark half" /> inferred
          </span>
          <span>
            <i className="mark dashed" /> suspected
          </span>
          <span>
            <i className="mark" /> goal
          </span>
          <span>
            <i className="mark hot" /> slipped
          </span>
          <span>dotted trail = sureness decayed as evidence aged</span>
        </p>
        {sel ? (
          <div className="readout" role="region" aria-label={`Readout: ${sel.title}`} ref={readoutRef} tabIndex={-1}>
            <div className="k" style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span className="lbl ink">{sel.title}</span>
              <button type="button" className="ctl" onClick={() => select(null)} aria-label="Close readout">
                Esc
              </button>
            </div>
            <div className="k">
              <span className="lbl">State</span>
              <span className={sel.state === "drifting" ? "hot" : ""}>{stateLabel(sel.state)}</span>
            </div>
            <div className="k">
              <span className="lbl">Kind</span>
              <span>{kindLabelOf(sel)}</span>
            </div>
            <div className="k">
              <span className="lbl">Claim</span>
              <span>{postureOf(sel)}</span>
            </div>
            <div className="k">
              <span className="lbl">Source</span>
              <span>{sel.sources.length ? sel.sources.map(sourceLabel).join(", ") : sourceLabel(sel.provenance)}</span>
            </div>
            <div className="k">
              <span className="lbl">Sure</span>
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <Meter value={sel.confidence} tone={sel.state === "drifting" ? "hot" : postureOf(sel) === "told" || postureOf(sel) === "evidenced" ? "default" : "dotted"} /> {pct(sel.confidence)}
              </span>
            </div>
            <div className="k">
              <span className="lbl">Evidence age</span>
              <span>{daysSince(sel.updatedAt ?? sel.createdAt, world.now) ?? "—"} d</span>
            </div>
            {sel.due && (
              <div className="k">
                <span className="lbl">{sel.state === "drifting" ? "Deadline passed" : "Deadline"}</span>
                <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span title={sel.dueSynthetic ? "Seed fixture deadline" : undefined}>{relDay(sel.due, world.now)}</span>
                </span>
              </div>
            )}
            {sel.driftRationale && (
              <div className="k" style={{ gridColumn: "1 / -1" }}>
                <span className="lbl hot">Why</span>
                <span>{sel.driftRationale}</span>
              </div>
            )}
          </div>
        ) : null}
        <div className="hero-foot">
          <p className="sentence">{world.loading ? "Reading the world-state…" : worldSentence(world)}</p>
          <Link to={ASK_SLIPPING} className="ctl primary">
            What's slipping?
          </Link>
        </div>
      </section>

      <aside className="rail" aria-label="Feeds">
        <Module label="Loops · confidence" index="G·01">
          {loopsShown.map((c) => {
            const posture = postureOf(c);
            const hot = c.state === "drifting";
            const kind = c.kind === "goal" ? "goal" : posture === "suspected" ? "suspected" : posture === "inferred" ? "inferred" : "told";
            const st = staleness(c.updatedAt ?? c.createdAt, world.now);
            const conf0 = c.confidence == null ? null : Math.min(1, c.confidence / Math.max(0.3, 1 - 0.7 * st));
            const days = daysSince(c.updatedAt ?? c.createdAt, world.now);
            return (
              <div key={c.id} className={`row loop ${hot ? "hot" : ""} ${c.state}`} onClick={() => select(c.id)} role="button" tabIndex={0} onKeyDown={(e) => (e.key === "Enter" || e.key === " " ? (e.preventDefault(), select(c.id)) : undefined)}>
                <i className="tick" aria-hidden="true" />
                <span className="t">
                  <Glyph kind={kind} hot={hot} /> {short(c.title)}
                </span>
                <span className="ro-stack">
                  <Spark from={conf0} to={c.confidence} hot={hot} dotted={kind !== "told"} label={`${pct(c.confidence)} sure${conf0 != null && c.confidence != null && conf0 - c.confidence > 0.02 ? `, down from ${pct(conf0)}` : ""}`} />
                  <span className={`ro ${hot ? "hot" : ""}`}>
                    {c.confidence == null ? "—" : c.confidence.toFixed(2)}
                    {conf0 != null && c.confidence != null && conf0 - c.confidence > 0.02 ? <span className="delta">▾{(conf0 - c.confidence).toFixed(2)}</span> : null}
                  </span>
                </span>
                <span className="s">
                  {stateLabel(c.state)} · {sourceLabel(c.provenance)} · <span className="ro">{days == null ? "—" : `${days}d`}</span> ago
                </span>
              </div>
            );
          })}
          {suspectedCount > 0 && (
            <div className="row dotted">
              <span className="t">{suspectedCount} suspected</span>
              <span className="lbl">in Needs you</span>
            </div>
          )}
        </Module>
        <Module label="Touched · 7 d" index="G·02">
          {inflows.map((f, i) => (
            <div key={f.k} className="row">
              <span className="t">{sourceLabel(f.k)}</span>
              <span className="num md">
                {f.n < 10 ? "0" : ""}
                <CountUp to={f.n} delay={200 + i * 90} reducedMotion={reducedMotion} />
              </span>
            </div>
          ))}
        </Module>
        <Module label="While you were away" index="G·03">
          {world.away.slice(0, 4).map((e) => (
            <div key={e.id} className={`row ${e.outcome === "failed" ? "hot" : ""}`}>
              <span className="t">{e.title}</span>
              <span className="ro">{ago(e.at, world.now)}</span>
              {e.outcome === "failed" && <span className="s">{humanFailure(e.body)}</span>}
            </div>
          ))}
          {world.away.length === 0 && <p className="muted">Quiet.</p>}
        </Module>
      </aside>
    </main>
  );
}
