import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { useRef, useState, type KeyboardEvent } from "react";
import { useNarrow } from "@/shared/lib";
import { memoryPoints, type MemoryPoint } from "../../lib/instruments/memory";

const W = 100;
const H = 60;
const FLOOR = 56;
const px = (x: number) => 4 + x * (W - 8);
const py = (y: number | null) => (y === null ? FLOOR : 50 - y * 44);

function Mark({ p, active }: { p: MemoryPoint; active: boolean }) {
  const cx = px(p.x);
  const cy = py(p.y);
  const cls = `tr-mark ${p.glyph}${active ? " active" : ""}`;
  if (p.glyph === "episode") return <rect className={cls} x={cx - 1.6} y={cy - 1.6} width={3.2} height={3.2} />;
  if (p.glyph === "profile") return <path className={cls} d={`M${cx},${cy - 2}L${cx + 2},${cy + 1.6}L${cx - 2},${cy + 1.6}Z`} />;
  return <circle className={cls} cx={cx} cy={cy} r={1.8} />;
}

/** What Ze remembered for this reply: relevance across, extraction confidence up. Live partials carry the confidence too. */
export function MemoryConstellation({ chunks }: { chunks: WsTraceUpdateFrame["memory_chunks"] | undefined }) {
  const narrow = useNarrow();
  const { points, ranked } = memoryPoints(chunks);
  const [focus, setFocus] = useState<number | null>(null);
  const refs = useRef<(SVGGElement | null)[]>([]);
  if (points.length === 0) return <p className="muted">Nothing from memory.</p>;

  if (narrow) {
    return (
      <ol className="tr-memory-list" aria-label="Memory used, most relevant first">
        {ranked.map((p) => (
          <li key={p.id}>
            <span className="ro">{Math.round(p.x * 100)}%</span> <span className="lbl">{p.glyph}</span> {p.text}
          </li>
        ))}
      </ol>
    );
  }

  const byX = [...points].sort((a, b) => a.x - b.x);
  function onKey(e: KeyboardEvent, p: MemoryPoint) {
    const i = byX.findIndex((q) => q.id === p.id);
    const next = e.key === "ArrowRight" || e.key === "ArrowUp" ? byX[i + 1] : e.key === "ArrowLeft" || e.key === "ArrowDown" ? byX[i - 1] : null;
    if (next) {
      e.preventDefault();
      refs.current[next.id]?.focus();
    }
  }
  const shown = focus !== null ? points[focus] : null;
  return (
    <figure className="tr-memory">
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Memory used: relevance across, extraction confidence up">
        <line className="tr-axis" x1={4} y1={50} x2={W - 4} y2={50} />
        <line className="tr-floor" x1={4} y1={FLOOR} x2={W - 4} y2={FLOOR} />
        {points.map((p) => (
          <g
            key={p.id}
            ref={(el) => {
              refs.current[p.id] = el;
            }}
            tabIndex={0}
            role="img"
            aria-label={`${p.glyph}, relevance ${Math.round(p.x * 100)}%${p.y === null ? ", no extraction confidence" : `, confidence ${Math.round(p.y * 100)}%`}: ${p.text}`}
            onMouseEnter={() => setFocus(p.id)}
            onMouseLeave={() => setFocus(null)}
            onFocus={() => setFocus(p.id)}
            onBlur={() => setFocus(null)}
            onKeyDown={(e) => onKey(e, p)}
          >
            <Mark p={p} active={focus === p.id} />
          </g>
        ))}
      </svg>
      <figcaption className="ro" aria-live="polite">
        {shown ? shown.text : `${points.length} from memory; dashed floor: no extraction confidence`}
      </figcaption>
    </figure>
  );
}
