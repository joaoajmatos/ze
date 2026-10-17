import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { concernChip, concernPosture, concernStateWords, pct, useMediaQuery, type Concern } from "@/shared/lib";
import { deadlinePhrase, markLabel } from "../lib/labels";
import { BANDS, H, ML, NOW_X, PH, PW, W, Y0, Y1, layoutMarks, xOfDays, yOf, type Mark } from "../lib/placement";
import { trailOf } from "../lib/trail";
import type { Reorder } from "../lib/useReorder";

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

function wrapTitle(title: string, max = 42): string[] {
  const lines: string[] = [];
  let cur = "";
  for (const w of title.split(" ")) {
    if ((cur + " " + w).trim().length > max && cur) {
      lines.push(cur);
      cur = w;
    } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 3);
}

interface Props {
  concerns: Concern[];
  now: Date;
  /** Concern key of the selected mark. */
  selected: string | null;
  onSelect: (key: string | null) => void;
  reorder: Reorder;
}

/** The mark fill for a posture: filled told, half inferred, dashed hollow suspected, hollow goal, plain hollow. */
function markStyle(m: Mark) {
  const c = m.concern;
  const posture = concernPosture(c);
  const hot = c.slipped;
  const color = hot ? "var(--coral)" : posture === "suspected" ? "var(--dim)" : "var(--main)";
  const fill =
    posture === "goal" || posture === "plain" || posture === "suspected"
      ? "var(--field)"
      : posture === "inferred"
        ? hot
          ? "url(#half-hot)"
          : "url(#half)"
        : color;
  return { posture, hot, color, fill, dash: posture === "suspected" ? "2 2" : undefined, isGoal: posture === "goal" };
}

/**
 * The world-state as a field: x = time left (slipped | now | this week | later | no deadline),
 * y = how sure Ze is. Mark = claim kind, colour = state (coral slipped). A dotted trail shows how
 * sureness decayed, drawn only from a recorded prior.
 */
export function FieldChart({ concerns, now, selected, onSelect, reorder }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const fieldRef = useRef<HTMLDivElement>(null);
  // k converts CSS px to viewBox units, so type renders at a true pixel size whatever the chart's width.
  const [k, setK] = useState(1.15);
  const coarse = useMediaQuery("(pointer: coarse)");
  useEffect(() => {
    const el = fieldRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setK(W / Math.max(200, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const marks = useMemo(() => layoutMarks(concerns, now, k), [concerns, now, k]);
  // The leader line ends on the most overdue slipped mark.
  const leadKey = useMemo(() => {
    const slipped = marks.filter((m) => m.concern.slipped);
    if (!slipped.length) return null;
    return [...slipped].sort((a, b) => (a.days ?? Infinity) - (b.days ?? Infinity))[0].concern.key;
  }, [marks]);

  const active = marks.find((m) => m.concern.key === (hover ?? selected)) ?? null;
  const calloutLines = active ? wrapTitle(active.concern.title, 46) : [];
  const calloutW = 330;
  const calloutH = 14 * calloutLines.length + 52;
  const calloutX = ML + 10;
  const calloutY = Y1 - calloutH - 10;
  const hit = coarse ? 60 : 26;

  return (
    <div className="field" ref={fieldRef} style={{ "--k": k } as CSSProperties}>
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

          {BANDS.map((b, i) => (
            <g key={b.id} className={`band ${b.hot ? "hot" : ""}`}>
              <rect x={ML + PW * b.from} y={Y0} width={PW * (b.to - b.from)} height={PH} fill={b.hot ? "url(#hatch)" : i % 2 ? "var(--band)" : "transparent"} />
              <text x={ML + PW * b.from + 10} y={Y0 - 10}>
                {b.label}
              </text>
            </g>
          ))}
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
                <text x={x} y={Y1 + 18} textAnchor="middle">
                  {t.label}
                </text>
              </g>
            );
          })}
          <text className="axis" x={ML - 8} y={Y0 - 10} textAnchor="end">
            ↑ sure
          </text>
          <text className="axis" x={ML + PW} y={Y1 + 34} textAnchor="end">
            time left →
          </text>
          <rect x={ML} y={Y0} width={PW} height={PH} fill="none" stroke="var(--hair-strong)" strokeWidth={1} />

          <line x1={NOW_X} x2={NOW_X} y1={Y0 - 4} y2={Y1 + 4} stroke="var(--cream)" strokeWidth={3} opacity={0.5} filter="url(#nowglow)" />
          <line x1={NOW_X} x2={NOW_X} y1={Y0 - 4} y2={Y1 + 4} stroke="var(--cream)" strokeWidth={1} />

          {marks.map((m) => {
            const trail = trailOf(m.concern.confidencePrior, m.concern.confidence);
            if (!trail) return null;
            const color = m.concern.slipped ? "var(--coral)" : "var(--main)";
            const y0 = yOf(trail.from);
            return (
              <g key={`t${m.concern.key}`} className="trail">
                <line x1={m.x} x2={m.x} y1={y0} y2={m.y + (y0 < m.y ? -7 : 7)} stroke={color} strokeWidth={1} strokeDasharray="1.5 3" opacity={0.7} />
                <line x1={m.x - 4} x2={m.x + 4} y1={y0} y2={y0} stroke={color} strokeWidth={1} opacity={0.7} />
              </g>
            );
          })}

          {active && (
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
                <tspan className={active.concern.slipped ? "hot" : ""}>{concernStateWords(active.concern)}</tspan>
                <tspan> · {concernChip(concernPosture(active.concern)) ?? active.concern.kind}</tspan>
              </text>
              <text className="callout-meta" x={calloutX + 10} y={calloutY + calloutH - 9}>
                <tspan>{active.concern.confidence != null ? `${pct(active.concern.confidence)} sure` : "not a claim"}</tspan>
                <tspan> · {deadlinePhrase(active.concern.due, now)}</tspan>
              </text>
            </g>
          )}

          {marks.map((m) => {
            const { hot, color, fill, dash, isGoal } = markStyle(m);
            const key = m.concern.key;
            const on = selected === key;
            const size = 11;
            const props = reorder.markProps(key);
            return (
              <g
                key={key}
                data-key={key}
                className={`pt ${hot ? "hot" : ""} ${on ? "on" : ""} ${leadKey === key ? "lead" : ""} ${reorder.lifted === key ? "lifted" : ""} ${reorder.target === key && reorder.lifted !== key ? "drop-target" : ""}`}
                role="button"
                tabIndex={0}
                aria-pressed={on}
                aria-roledescription="mark"
                aria-label={markLabel(m, now)}
                onClick={() => {
                  if (reorder.consumeClick()) return;
                  onSelect(on ? null : key);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    onSelect(on ? null : key);
                    return;
                  }
                  props.onKeyDown(e);
                }}
                onPointerDown={props.onPointerDown}
                onPointerEnter={() => {
                  props.onPointerEnter();
                  setHover(key);
                }}
                onPointerLeave={() => {
                  props.onPointerLeave();
                  setHover(null);
                }}
                onFocus={() => setHover(key)}
                onBlur={() => setHover(null)}
              >
                <title>{m.concern.title}</title>
                <circle className="hit" cx={m.x} cy={m.y} r={hit} fill="transparent" />
                {(on || hover === key || reorder.lifted === key || reorder.target === key) && (
                  <g className="bracket" stroke="var(--cream)" strokeWidth={1} fill="none">
                    <path d={`M${m.x - 11},${m.y - 7}v-4h4M${m.x + 11},${m.y - 7}v-4h-4M${m.x - 11},${m.y + 7}v4h4M${m.x + 11},${m.y + 7}v4h-4`} />
                  </g>
                )}
                {Math.abs(m.ly - m.y) > 9 && <line x1={m.x + (m.right ? 7 : -7)} y1={m.y} x2={m.right ? m.lx - 3 : m.lx + 3} y2={m.ly} stroke="var(--hair-strong)" strokeWidth={1} />}
                <rect x={m.x - size / 2} y={m.y - size / 2} width={size} height={size} fill={fill} stroke={color} strokeWidth={1.5} strokeDasharray={dash} transform={isGoal ? `rotate(45 ${m.x} ${m.y})` : undefined} />
                <text className="lbl-wide" x={m.lx} y={m.ly + 4.5 * k} textAnchor={m.right ? "start" : "end"}>
                  {m.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="sr-only" role="status" aria-live="polite">
        {reorder.announcement}
      </p>
    </div>
  );
}
