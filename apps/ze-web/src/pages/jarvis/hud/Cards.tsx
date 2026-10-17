import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { goalPath, workflowPath } from "@/shared/config";
import { CountUp, Meter, Module } from "@/shared/ui";
import type { Component } from "../model/compose";
import { ago, hhmm, pct, relDay, sourceLabel, stateLabel } from "../model/format";
import { kindLabelOf, postureOf, short } from "../model/hud";
import type { Concern, World } from "../model/world";

interface CardProps {
  c: Component;
  world: World;
  index: number;
  delay: number;
  reducedMotion: boolean;
  tools: ReactNode;
  onTrack?: (loopId: string, kind: "confirm" | "drop") => void;
  busyLoop?: string | null;
  onOffer?: (choice: "draft" | "later") => void;
  queued?: "draft" | "later" | null;
}

const idx = (i: number) => String(i + 1).padStart(2, "0");

const DOW = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"];
/** Plain words for the common cron shapes; the raw expression otherwise. */
export function cronText(cron: string | null): string {
  if (!cron) return "manual";
  const m = cron.trim().split(/\s+/);
  if (m.length !== 5) return cron;
  const [min, hour, , , dow] = m;
  const time = /^\d+$/.test(hour) && /^\d+$/.test(min) ? `${hour.padStart(2, "0")}:${min.padStart(2, "0")}` : null;
  if (!time) return cron;
  if (dow === "*") return `Daily ${time}`;
  if (dow === "1-5") return `Weekdays ${time}`;
  if (/^\d$/.test(dow)) return `${DOW[Number(dow)]} ${time}`;
  return cron;
}

export function Card(p: CardProps) {
  const { c, world, index, delay, reducedMotion, tools } = p;
  switch (c.kind) {
    case "timeline":
      return (
        <Module label={c.title} index={`${idx(index)} · timeline`} tools={tools}>
          <SlipTimeline items={c.items} world={world} />
        </Module>
      );
    case "evidence": {
      const s = c.slip;
      const hot = s.kind === "slipped";
      return (
        <Module label={hot ? "Slipped" : "At risk"} index={`${idx(index)} · ${sourceLabel(s.concern.provenance)}`} tone={hot ? "hot" : "default"} tools={tools}>
          <p className="sentence" style={{ fontSize: "1.0625rem" }}>
            {short(s.concern.title)}
          </p>
          <div className="rule" />
          {hot && (
            <div className="row">
              <span className="t muted">{s.overdueLabel === "past deadline" ? "Past deadline" : "Quiet for"}</span>
              <span className="num lg hot">
                {s.overdueDays == null ? "—" : <CountUp to={s.overdueDays} delay={delay + 320} reducedMotion={reducedMotion} />}
                <span className="lbl hot" style={{ marginLeft: 4 }}>
                  d
                </span>
              </span>
            </div>
          )}
          <div className="row">
            <span className="t muted">Sure</span>
            <Meter value={s.concern.confidence} tone={hot ? "hot" : "default"} animate delay={delay + 260} label={`${pct(s.concern.confidence)} sure`} />
          </div>
          <p className="muted" style={{ marginTop: 8, fontSize: "0.875rem" }}>
            {s.why}
          </p>
          <div className="chips">
            {(s.concern.sources.length ? s.concern.sources : [s.concern.provenance ?? ""]).map((src) => (
              <span key={src} className="chip solid">
                {sourceLabel(src)}
              </span>
            ))}
            <span className="chip">{postureOf(s.concern)}</span>
            {!hot && <span className="chip dotted">risk is Ze's read</span>}
          </div>
        </Module>
      );
    }
    case "loop": {
      const l = c.concern;
      const hot = l.state === "drifting";
      const inferred = l.kind === "hypothesis";
      return (
        <Module label={inferred ? "Also watching" : stateLabel(l.state)} index={`${idx(index)} · ${kindLabelOf(l)}`} tone={hot ? "hot" : inferred || l.state === "suspected" ? "dotted" : "default"} tools={tools}>
          <p className="sentence" style={{ fontSize: "1.0625rem" }}>
            {inferred ? `${l.title}?` : short(l.title)}
          </p>
          <div className="rule" />
          <div className="row">
            <span className="t muted">Sure</span>
            <Meter value={l.confidence} tone={hot ? "hot" : inferred || l.state === "suspected" ? "dotted" : "default"} animate delay={delay + 260} label={`${pct(l.confidence)} sure`} />
          </div>
          {l.driftRationale && (
            <p className="muted" style={{ marginTop: 8, fontSize: "0.875rem" }}>
              {l.driftRationale}
            </p>
          )}
          <div className="chips">
            <span className="chip solid">{sourceLabel(l.provenance)}</span>
            {inferred ? <span className="chip dotted">asked, not stated</span> : <span className="chip">{postureOf(l)}</span>}
            {l.updatedAt && <span className="chip">updated {ago(l.updatedAt, world.now)}</span>}
          </div>
        </Module>
      );
    }
    case "person":
      return (
        <Module label="Person" index={`${idx(index)} · ${c.person.role ?? c.person.type}`} tools={tools}>
          <p className="sentence" style={{ fontSize: "1.0625rem" }}>
            {c.person.name}
          </p>
          <p className="muted" style={{ fontSize: "0.875rem", marginTop: 4 }}>
            Named in {c.linked[0] ? `“${short(c.linked[0].title)}”` : "a concern"}.
          </p>
          <div className="rule" />
          <div className="row">
            <span className="t muted">Linked concerns</span>
            <span className="num md">{String(c.linked.length).padStart(2, "0")}</span>
          </div>
          {c.linked.slice(0, 3).map((l) => (
            <div key={l.id} className={`row ${l.state === "drifting" ? "hot" : ""}`}>
              <span className="t">{short(l.title)}</span>
              <span className="lbl">{stateLabel(l.state)}</span>
            </div>
          ))}
          <div className="chips">
            <span className="chip">{c.person.degree} graph links</span>
          </div>
        </Module>
      );
    case "goal": {
      const g = c.goal;
      return (
        <Module label={g.openGate ? "Goal · gate" : "Goal"} index={`${idx(index)} · ${g.done}/${g.total} milestones`} tone={g.openGate ? "cream" : "default"} tools={tools}>
          <p className="sentence" style={{ fontSize: "1.0625rem" }}>
            {g.title}
          </p>
          <p className="muted" style={{ fontSize: "0.875rem", marginTop: 4 }}>
            {g.objective}
          </p>
          <div className="segments" role="img" aria-label={`${g.done} of ${g.total} milestones done`}>
            {g.milestones.map((m, i) => (
              <i key={i} className={m.status === "completed" ? "done" : m.status === "in_progress" ? "live" : ""} title={m.title} />
            ))}
          </div>
          {g.milestones.map((m) => (
            <div key={m.title} className="row">
              <span className="t">{m.title}</span>
              <span className={`lbl ${m.status === "in_progress" ? "on" : ""}`}>{m.status.replace("_", " ")}</span>
            </div>
          ))}
          {g.openGate && (
            <p style={{ marginTop: 10, fontSize: "0.875rem", color: "var(--cream)" }}>
              Gate waiting on you: {g.openGate.title}
              {g.openGate.summary ? <span className="muted"> · {g.openGate.summary}</span> : null}
            </p>
          )}
          <div className="actions">
            <Link to={goalPath(g.id)} className={`ctl ${g.openGate ? "primary" : ""}`}>
              {g.openGate ? "Open and decide" : "Open goal"}
            </Link>
          </div>
        </Module>
      );
    }
    case "workflow": {
      const w = c.workflow;
      const fails = w.runs.filter((r) => !r.ok).length;
      return (
        <Module label="Workflow" index={`${idx(index)} · ${w.enabled ? "on" : "off"}`} tools={tools}>
          <p className="sentence" style={{ fontSize: "1.0625rem" }}>
            {w.name}
          </p>
          <div className="rule" />
          <div className="row">
            <span className="t muted">Schedule</span>
            <span className="lbl">{cronText(w.schedule)}</span>
          </div>
          <div className="row">
            <span className="t muted">Next run</span>
            <span className="lbl">{w.nextRun ? `${relDay(w.nextRun, world.now)} ${hhmm(w.nextRun)}` : "—"}</span>
          </div>
          <div className="row">
            <span className="t muted">Recent runs</span>
            <span className="runs" aria-label={`${w.runs.length - fails} ok, ${fails} failed`}>
              {w.runs.map((r) => (
                <i key={r.id} className={r.ok ? "ok" : "fail"} />
              ))}
            </span>
          </div>
          <div className="actions">
            <Link to={workflowPath(w.id)} className="ctl">
              Open workflow
            </Link>
          </div>
        </Module>
      );
    }
    case "decision": {
      const d = c.decision;
      const loopId = d.kind === "suspicion" ? d.id.replace(/^loop:/, "") : null;
      const busy = p.busyLoop === loopId;
      return (
        <Module label={d.kind === "gate" ? "Gate" : d.kind === "held_write" ? "Held write" : d.kind === "suspicion" ? "Confirm?" : "Review"} index={`${idx(index)} · ${d.origin}`} tone={d.kind === "suspicion" ? "dotted" : "cream"} tools={tools}>
          <p className="sentence" style={{ fontSize: "1.0625rem" }}>
            {d.title}
          </p>
          {d.detail && (
            <p className="muted" style={{ fontSize: "0.875rem", marginTop: 6 }}>
              {d.detail}
            </p>
          )}
          {d.confidence != null && (
            <div className="row">
              <span className="t muted">Sure</span>
              <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                <Meter value={d.confidence} tone="dotted" animate delay={delay + 260} label={`${pct(d.confidence)} sure`} /> <span className="lbl">{pct(d.confidence)}</span>
              </span>
            </div>
          )}
          <div className="actions">
            {loopId && p.onTrack ? (
              <>
                <button type="button" className="ctl primary" disabled={busy} onClick={() => p.onTrack!(loopId, "confirm")}>
                  Yes, track it
                </button>
                <button type="button" className="ctl" disabled={busy} onClick={() => p.onTrack!(loopId, "drop")}>
                  Drop
                </button>
              </>
            ) : d.href ? (
              <Link to={d.href} className="ctl primary">
                Open and decide
              </Link>
            ) : null}
          </div>
        </Module>
      );
    }
    case "chart": {
      const max = Math.max(1, ...c.series.map((s) => s.value));
      return (
        <Module label={c.title} index={`${idx(index)} · chart`} tools={tools}>
          <div className="bars" role="img" aria-label={`${c.series.length} runs, ${c.series.filter((s) => !s.ok).length} failed`}>
            {c.series.map((s, i) => (
              <i key={i} className={s.ok ? "" : "fail"} style={{ height: `${Math.max(6, (s.value / max) * 100)}%` }} title={`${s.label}: ${s.value}${c.unit}${s.ok ? "" : " · failed"}`} />
            ))}
          </div>
          <div className="row">
            <span className="t muted">Longest</span>
            <span className="num md">
              {max}
              <span className="lbl" style={{ marginLeft: 4 }}>
                {c.unit}
              </span>
            </span>
          </div>
        </Module>
      );
    }
    case "facts":
      return (
        <Module label={c.title} index={`${idx(index)} · memory`} tools={tools}>
          {c.facts.map((f) => (
            <div key={f.id} className={`row ${f.reviewed ? "" : "dotted"}`}>
              <span className="t">{f.value}</span>
              <Meter value={f.confidence} tone={f.reviewed ? "default" : "dotted"} label={`${pct(f.confidence)} sure`} />
              <span className="s">
                {f.reviewed ? "reviewed" : "unreviewed"} · {f.agent} · {ago(new Date(f.created_at), world.now)}
              </span>
            </div>
          ))}
        </Module>
      );
    case "sentence":
      return (
        <Module label="Ze's answer" tone="default" as="article" headless tools={tools}>
          <div aria-live="polite">
            <p className="sentence" style={{ maxWidth: "72ch" }}>
              {c.sentence} {c.offer}
            </p>
          </div>
          {c.note && <p className="muted" style={{ marginTop: 8, fontSize: "0.875rem" }}>{c.note}</p>}
          {p.queued === "draft" && c.target ? (
            <p className="muted" style={{ marginTop: 10, maxWidth: "72ch" }}>
              Noted: a draft on “{short(c.target.title)}” would be queued for tonight and held for your OK, never sent on its own. Nothing was queued yet; this surface is a prototype.
            </p>
          ) : p.queued === "later" && c.target ? (
            <p className="muted" style={{ marginTop: 10, maxWidth: "72ch" }}>
              Noted: “{short(c.target.title)}” would move a week out and the nudges would pause until then. Nothing was changed yet; this surface is a prototype.
            </p>
          ) : null}
          {c.offer && c.target && (
            <>
              <div className="actions">
                <button type="button" className="ctl primary" disabled={p.queued != null} onClick={() => p.onOffer?.("draft")}>
                  {`Draft it tonight · “${short(c.target.title).slice(0, 26)}${short(c.target.title).length > 26 ? "…" : ""}”`}
                </button>
                <button type="button" className="ctl" disabled={p.queued != null} onClick={() => p.onOffer?.("later")}>
                  Give it a week
                </button>
              </div>
              {p.queued == null && (
                <p className="muted" style={{ marginTop: 8, fontSize: "0.8125rem" }}>
                  A draft is held for your OK. Nothing is sent without you.
                </p>
              )}
            </>
          )}
        </Module>
      );
  }
}

/** A horizontal slip timeline: past 7 days to the next 7, with the NOW line. */
function SlipTimeline({ items, world }: { items: Concern[]; world: World }) {
  const W = 920;
  const H = 150;
  const ML = 16;
  const MR = 16;
  const PW = W - ML - MR;
  const xOf = (days: number) => ML + PW * (Math.min(7, Math.max(-7, days)) + 7) / 14;
  const rows: { c: Concern; x: number; y: number; hot: boolean }[] = [];
  const lanes: number[] = [];
  items.forEach((c) => {
    const days = c.due ? (c.due.getTime() - world.now.getTime()) / 86400_000 : -7;
    const x = xOf(days);
    let lane = lanes.findIndex((lx) => Math.abs(lx - x) > 250);
    if (lane === -1) {
      lanes.push(x);
      lane = lanes.length - 1;
    } else lanes[lane] = x;
    rows.push({ c, x, y: 34 + lane * 26, hot: c.state === "drifting" });
  });
  const now = xOf(0);
  return (
    <svg viewBox={`0 0 ${W} ${Math.max(H, 50 + lanes.length * 26)}`} className="timeline" role="img" aria-label={`${items.length} concerns on a two-week timeline`}>
      <defs>
        <pattern id="hatch-t" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--coral)" strokeWidth="1" opacity="0.25" />
        </pattern>
      </defs>
      <rect x={ML} y={14} width={now - ML} height={Math.max(H, 50 + lanes.length * 26) - 28} fill="url(#hatch-t)" />
      {[-7, -3, 0, 2, 4, 7].map((d) => (
        <g key={d} className="grid">
          <line x1={xOf(d)} x2={xOf(d)} y1={14} y2={Math.max(H, 50 + lanes.length * 26) - 14} stroke={d === 0 ? "var(--cream)" : "var(--hair)"} strokeWidth={d === 0 ? 1.25 : 1} />
          <text className={Math.abs(d) === 7 || d === 0 ? "" : "tick-minor"} x={xOf(d)} y={10} textAnchor="middle">
            {d === 0 ? "now" : d > 0 ? `+${d}d` : `${d}d`}
          </text>
        </g>
      ))}
      {rows.map(({ c, x, y, hot }) => (
        <g key={c.id} className={`pt ${hot ? "hot" : ""}`}>
          <title>{c.title}</title>
          <rect x={x - 4.5} y={y - 4.5} width={9} height={9} fill={hot ? "var(--coral)" : c.state === "suspected" ? "var(--field)" : "var(--main)"} stroke={hot ? "var(--coral)" : "var(--main)"} strokeWidth={1.5} strokeDasharray={c.state === "suspected" ? "2 2" : undefined} />
          <text className="lbl-wide" x={x + 12} y={y + 4}>
            {short(c.title).slice(0, 34)}
            {short(c.title).length > 34 ? "…" : ""}
          </text>
        </g>
      ))}
    </svg>
  );
}
