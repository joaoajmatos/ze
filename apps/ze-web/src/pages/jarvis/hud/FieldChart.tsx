import { useEffect, useMemo, useRef, useState } from "react";
import { dayDiff, pct, relDay, stateLabel } from "../model/format";
import { staleness } from "../model/format";
import { kindLabelOf, postureOf, short, type Posture } from "../model/hud";
import type { Concern, World } from "../model/world";

const W = 920;
const H = 540;
const ML = 56;
const MR = 48;
const MT = 30;
const MB = 40;
const PW = W - ML - MR;
const PH = H - MT - MB;
const Y0 = MT;
const Y1 = MT + PH;

/** Bands along x: time left. Fractions of the plot width. */
const NARROW_BAND: Record<string, string> = { slipped: "Slipped", week: "Week", later: "Later", none: "No date" };
const BANDS: { id: string; label: string; from: number; to: number; hot?: boolean }[] = [
  { id: "slipped", label: "Slipped", from: 0, to: 0.2, hot: true },
  { id: "week", label: "This week", from: 0.2, to: 0.52 },
  { id: "later", label: "Later", from: 0.52, to: 0.78 },
  { id: "none", label: "No deadline", from: 0.78, to: 1 },
];
const NOW_X = ML + PW * 0.2;
const NARROW_TICKS = new Set(["-7d", "now", "+7d", "+30d", "no date"]);
const TICKS: { d: number | null; label: string }[] = [
  { d: -7, label: "-7d" },
  { d: -3, label: "-3d" },
  { d: 0, label: "now" },
  { d: 2, label: "+2d" },
  { d: 4, label: "+4d" },
  { d: 7, label: "+7d" },
  { d: 14, label: "+14d" },
  { d: 30, label: "+30d" },
  { d: null, label: "no date" },
];

function xOfDays(d: number): number {
  if (d <= 0) return ML + PW * (0.2 * (1 - Math.min(7, -d) / 7));
  if (d <= 7) return ML + PW * (0.2 + 0.32 * (d / 7));
  return ML + PW * (0.52 + 0.26 * Math.min(1, Math.log(d / 7) / Math.log(30 / 7)));
}
function xOfNone(i: number, n: number): number {
  return ML + PW * (0.8 + (0.18 * (i + 0.5)) / Math.max(1, n));
}
function yOf(conf: number): number {
  return Y0 + PH * (1 - Math.min(1, Math.max(0, conf)));
}
function daysLeft(c: Concern, now: Date): number | null {
  if (!c.due) return null;
  return (c.due.getTime() - now.getTime()) / 86400_000;
}

const LABEL_MAX = 36;
const CHAR_W = 7;
interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}
function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}
function place(box: Box, placed: Box[]): Box {
  let best = box;
  for (let step = 0; step < 11; step++) {
    const dy = step === 0 ? 0 : (step % 2 ? 1 : -1) * Math.ceil(step / 2) * (box.h + 1);
    const cand = { ...box, y: box.y + dy };
    if (!placed.some((p) => overlaps(cand, p))) {
      best = cand;
      break;
    }
  }
  placed.push(best);
  return best;
}
function shortLabel(title: string): string {
  const t = short(title);
  if (t.length <= LABEL_MAX) return t;
  const cut = t.slice(0, LABEL_MAX + 1);
  const at = cut.lastIndexOf(" ");
  return `${(at > 10 ? cut.slice(0, at) : cut.slice(0, LABEL_MAX)).replace(/[,:;]$/, "")}…`;
}
function wrapTitle(title: string, max = 42): string[] {
  const words = title.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > max && cur) {
      lines.push(cur);
      cur = w;
    } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 3);
}

interface Pt {
  c: Concern;
  x: number;
  y: number;
  y0: number; // where sureness started before decay
  posture: Posture;
  isGoal: boolean;
  label: string;
  lx: number;
  ly: number;
  right: boolean;
  n: number;
  days: number | null;
}

interface Props {
  world: World;
  selected: string | null;
  onSelect: (id: string | null) => void;
  narrow: boolean;
}

/**
 * The world-state as a field: x = time left (slipped | now | this week | later | no deadline),
 * y = how sure Ze is. Mark = claim kind (filled told, half inferred, dashed suspected, hollow goal),
 * color = state (coral slipped). A dotted trail shows how sureness decayed as evidence aged.
 */
export function FieldChart({ world, selected, onSelect, narrow }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const fieldRef = useRef<HTMLDivElement>(null);
  // k converts CSS px to viewBox units, so type renders at a true pixel size whatever the chart's width.
  const [k, setK] = useState(1.15);
  useEffect(() => {
    const el = fieldRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setK(W / Math.max(200, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const pts = useMemo(() => {
    const placed: Box[] = [];
    const none = world.concerns.filter((c) => daysLeft(c, world.now) == null).sort((a, b) => (b.confidence ?? 0.5) - (a.confidence ?? 0.5));
    const out: Pt[] = [];
    const lineH = 15 * k;
    world.concerns.forEach((c, i) => {
      const d = daysLeft(c, world.now);
      const x = d == null ? xOfNone(none.indexOf(c), none.length) : xOfDays(d);
      const conf = c.confidence ?? 0.5;
      const st = staleness(c.updatedAt ?? c.createdAt, world.now);
      const conf0 = Math.min(1, conf / Math.max(0.3, 1 - 0.7 * st));
      // The no-deadline band has no x meaning, so its points sit in fixed lanes by rank (labels left).
      const laneI = d == null ? none.indexOf(c) : -1;
      const y = laneI >= 0 ? Y0 + 52 + laneI * Math.max(lineH + 6, 22) : yOf(conf);
      const right = laneI >= 0 ? false : x < W - 230 * k;
      const label = shortLabel(c.title);
      const w = label.length * CHAR_W * k;
      const box = place({ x: right ? x + 13 : x - 13 - w, y: y - lineH / 2, w, h: lineH }, placed);
      out.push({
        c,
        x,
        y,
        y0: laneI >= 0 ? y : yOf(conf0),
        posture: postureOf(c),
        isGoal: c.kind === "goal",
        label,
        lx: right ? box.x : box.x + w,
        ly: box.y + lineH / 2,
        right,
        n: i + 1,
        days: d,
      });
    });
    return out;
  }, [world, k]);

  const active = pts.find((p) => p.c.id === (hover ?? selected)) ?? null;
  const calloutLines = active ? wrapTitle(active.c.title, 46) : [];
  const calloutW = 330;
  const calloutH = 14 * calloutLines.length + 52;
  const calloutX = ML + 10;
  const calloutY = Y1 - calloutH - 10;

  return (
    <div className="field" ref={fieldRef} style={{ "--k": k } as React.CSSProperties}>
      {!narrow && (
      <div className="field-plot">
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="World-state field: time left across, how sure Ze is up, mark shape is the claim kind, coral is slipped">
        <defs>
          <pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="8" stroke="var(--coral)" strokeWidth="1" opacity="0.28" />
          </pattern>
          <filter id="nowglow" x="-400%" y="-10%" width="900%" height="120%">
            <feGaussianBlur stdDeviation="3" />
          </filter>
          <linearGradient id="half" x1="0" y1="0" x2="1" y2="1">
            <stop offset="50%" stopColor="var(--main)" />
            <stop offset="50%" stopColor="var(--field)" />
          </linearGradient>
          <linearGradient id="half-hot" x1="0" y1="0" x2="1" y2="1">
            <stop offset="50%" stopColor="var(--coral)" />
            <stop offset="50%" stopColor="var(--field)" />
          </linearGradient>
        </defs>

        {/* bands */}
        {BANDS.map((b, i) => (
          <g key={b.id} className={`band ${b.hot ? "hot" : ""}`}>
            <rect x={ML + PW * b.from} y={Y0} width={PW * (b.to - b.from)} height={PH} fill={b.hot ? "url(#hatch)" : i % 2 ? "var(--band)" : "transparent"} />
            <text x={ML + PW * b.from + 10} y={Y0 - 10}>
              {narrow ? NARROW_BAND[b.id] : b.label}
            </text>
          </g>
        ))}
        {/* hairline grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <g key={v} className="grid">
            <line x1={ML} x2={ML + PW} y1={yOf(v)} y2={yOf(v)} stroke="var(--hair)" strokeWidth={1} />
            <text x={ML - 8} y={yOf(v) + 3.5} textAnchor="end">
              {v.toFixed(2).replace(/^0/, "").replace("1.00", "1.0").replace(".00", "0")}
            </text>
          </g>
        ))}
        {TICKS.map((t) => {
          const x = t.d == null ? ML + PW * 0.89 : xOfDays(t.d);
          return (
            <g key={t.label} className="grid">
              {t.d !== 0 && <line x1={x} x2={x} y1={Y0} y2={Y1} stroke="var(--hair)" strokeWidth={1} />}
              <line x1={x} x2={x} y1={Y1} y2={Y1 + 5} stroke="var(--hair-strong)" strokeWidth={1} />
              {(!narrow || NARROW_TICKS.has(t.label)) && <text x={x} y={Y1 + 18} textAnchor="middle">
                {t.label}
              </text>}
            </g>
          );
        })}
        {!narrow && (
          <text className="axis" x={ML + 8} y={Y0 + 16} textAnchor="start">
            ↑ how sure Ze is
          </text>
        )}
        <text className="axis" x={ML + PW} y={Y1 + 34} textAnchor="end">
          time left →
        </text>
        {/* plot frame */}
        <rect x={ML} y={Y0} width={PW} height={PH} fill="none" stroke="var(--hair-strong)" strokeWidth={1} />

        {/* the NOW line, glowing */}
        <line x1={NOW_X} x2={NOW_X} y1={Y0 - 4} y2={Y1 + 4} stroke="var(--cream)" strokeWidth={3} opacity={0.5} filter="url(#nowglow)" />
        <line x1={NOW_X} x2={NOW_X} y1={Y0 - 4} y2={Y1 + 4} stroke="var(--cream)" strokeWidth={1} />

        {/* confidence trails */}
        {pts.map((p) =>
          Math.abs(p.y0 - p.y) > 4 ? (
            <g key={`t${p.c.id}`} className="trail">
              <line x1={p.x} x2={p.x} y1={p.y0} y2={p.y - 7} stroke={p.c.state === "drifting" ? "var(--coral)" : "var(--main)"} strokeWidth={1} strokeDasharray="1.5 3" opacity={0.7} />
              <line x1={p.x - 4} x2={p.x + 4} y1={p.y0} y2={p.y0} stroke={p.c.state === "drifting" ? "var(--coral)" : "var(--main)"} strokeWidth={1} opacity={0.7} />
            </g>
          ) : null,
        )}

        {/* leader line + callout for the active point */}
        {active && !narrow && (
          <g className="callout" aria-hidden="true">
            <line x1={active.x} y1={active.y} x2={active.x > calloutX + calloutW ? calloutX + calloutW : active.x < calloutX ? calloutX : active.x} y2={active.y > calloutY ? calloutY + calloutH / 2 : calloutY} stroke="var(--cream)" strokeWidth={1} opacity={0.7} />
            <rect x={calloutX} y={calloutY} width={calloutW} height={calloutH} fill="var(--field)" stroke="var(--hair-strong)" strokeWidth={1} />
            <text className="callout-title" x={calloutX + 10} y={calloutY + 18}>
              {calloutLines.map((l, i) => (
                <tspan key={i} x={calloutX + 10} dy={i === 0 ? 0 : 14}>
                  {l}
                </tspan>
              ))}
            </text>
            <text className="callout-meta" x={calloutX + 10} y={calloutY + calloutH - 22}>
              <tspan className={active.c.state === "drifting" ? "hot" : ""}>{stateLabel(active.c.state)}</tspan>
              <tspan> · {kindLabelOf(active.c)} · {active.posture}</tspan>
            </text>
            <text className="callout-meta" x={calloutX + 10} y={calloutY + calloutH - 9}>
              <tspan>{active.c.confidence != null ? `${pct(active.c.confidence)} sure` : "sureness unknown"}</tspan>
              <tspan>{active.days != null ? ` · deadline ${active.c.due ? relDay(active.c.due, world.now) : ""}` : " · no deadline"}</tspan>
            </text>
          </g>
        )}

        {/* points */}
        {pts.map((p) => {
          const hot = p.c.state === "drifting";
          const on = selected === p.c.id;
          const color = hot ? "var(--coral)" : p.c.state === "suspected" ? "var(--dim)" : "var(--main)";
          const size = 11;
          const fill = p.isGoal ? "var(--field)" : p.posture === "told" || p.posture === "evidenced" ? color : p.posture === "inferred" ? (hot ? "url(#half-hot)" : "url(#half)") : "var(--field)";
          const dash = p.posture === "suspected" ? "2 2" : undefined;
          return (
            <g
              key={p.c.id}
              className={`pt ${hot ? "hot" : ""} ${on ? "on" : ""}`}
              role="button"
              tabIndex={0}
              aria-pressed={on}
              aria-label={`${short(p.c.title)}: ${stateLabel(p.c.state)}, ${kindLabelOf(p.c)}, ${p.posture}${p.c.confidence != null ? `, ${pct(p.c.confidence)} sure` : ""}${p.days == null ? ", no deadline" : p.c.due && dayDiff(p.c.due, world.now) < 0 ? `, ${-dayDiff(p.c.due, world.now)} days past deadline` : `, deadline ${p.c.due ? relDay(p.c.due, world.now) : ""}`}`}
              onClick={() => onSelect(on ? null : p.c.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(on ? null : p.c.id);
                }
              }}
              onMouseEnter={() => setHover(p.c.id)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(p.c.id)}
              onBlur={() => setHover(null)}
            >
              <title>{p.c.title}</title>
              <circle className="hit" cx={p.x} cy={p.y} r={26} fill="transparent" />
              {(on || hover === p.c.id) && (
                <g className="bracket" stroke="var(--cream)" strokeWidth={1} fill="none">
                  <path d={`M${p.x - 11},${p.y - 7}v-4h4M${p.x + 11},${p.y - 7}v-4h-4M${p.x - 11},${p.y + 7}v4h4M${p.x + 11},${p.y + 7}v4h-4`} />
                </g>
              )}
              {Math.abs(p.ly - p.y) > 9 && <line x1={p.x + (p.right ? 7 : -7)} y1={p.y} x2={p.right ? p.lx - 3 : p.lx + 3} y2={p.ly} stroke="var(--hair-strong)" strokeWidth={1} />}
              <rect x={p.x - size / 2} y={p.y - size / 2} width={size} height={size} fill={fill} stroke={color} strokeWidth={1.5} strokeDasharray={dash} transform={p.isGoal ? `rotate(45 ${p.x} ${p.y})` : undefined} />
              <text className="lbl-wide" x={p.lx} y={p.ly + 4.5 * k} textAnchor={p.right ? "start" : "end"}>
                {p.label}
              </text>
              <text className="lbl-narrow" x={p.x} y={p.y + 22} textAnchor="middle">
                {p.n}
              </text>
            </g>
          );
        })}
      </svg>
      </div>
      )}
      {narrow && (
        <div className="field-list">
          {BANDS.map((b) => {
            const group = pts.filter((p) => (p.days == null ? b.id === "none" : b.id === "slipped" ? p.days < 0 : b.id === "week" ? p.days >= 0 && p.days <= 7 : p.days > 7));
            if (!group.length) return null;
            return (
              <section key={b.id} className={`field-band ${b.hot ? "hot" : ""}`} aria-label={b.label}>
                <h3 className={`lbl ${b.hot ? "hot" : ""}`}>
                  {b.label} · {group.length}
                </h3>
                <ol className="field-key">
                  {group.map((p) => (
                    <li key={p.c.id} className={p.c.state === "drifting" ? "hot" : ""}>
                      <button type="button" onClick={() => onSelect(selected === p.c.id ? null : p.c.id)} aria-pressed={selected === p.c.id}>
                        <i className={`glyph ${p.isGoal ? "goal" : p.posture === "inferred" ? "inferred" : p.posture === "suspected" ? "suspected" : "told"} ${p.c.state === "drifting" ? "hot" : ""}`} aria-hidden="true" />
                        <span className="field-title">{short(p.c.title)}</span>
                        <span className="ro">{p.c.confidence == null ? "—" : p.c.confidence.toFixed(2)}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
