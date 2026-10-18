import type { MilestoneResponse } from "@myguyze/ze-client";
import { useNarrow } from "@/shared/lib";

const STATE: Record<string, string> = {
  completed: "done",
  in_progress: "in progress",
  pending: "not started",
  skipped: "skipped",
  held: "on hold",
};
const stateWord = (s: string) => STATE[s] ?? s.replace(/_/g, " ");
const isDone = (m: MilestoneResponse) => m.status === "completed";
const isActive = (m: MilestoneResponse) => m.status === "in_progress";
const timeOf = (m: MilestoneResponse) => new Date((isDone(m) && m.completed_at) || m.created_at).getTime();
const day = (t: number) => new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });

const W = 600;
const PAD = 14;

/** Milestones on a time axis: done filled, active ringed, the rest hollow. A list on phones. */
export function MilestoneField({ milestones }: { milestones: MilestoneResponse[] }) {
  const narrow = useNarrow();
  const ordered = [...milestones].sort((a, b) => a.sequence - b.sequence);
  if (ordered.length === 0) return <p className="muted">No milestones yet.</p>;

  if (narrow) {
    return (
      <ol className="milestone-list">
        {ordered.map((m) => (
          <li key={m.id} className={`row ${isDone(m) ? "done" : ""}`}>
            <span className="t">{m.title}</span>
            <span className="lbl">{stateWord(m.status)}</span>
          </li>
        ))}
      </ol>
    );
  }

  const times = ordered.map(timeOf);
  const lo = Math.min(...times);
  const hi = Math.max(...times);
  const x = (m: MilestoneResponse, i: number) =>
    hi === lo ? PAD + (i / Math.max(ordered.length - 1, 1)) * (W - 2 * PAD) : PAD + ((timeOf(m) - lo) / (hi - lo)) * (W - 2 * PAD);
  const next = ordered.find((m) => !isDone(m) && m.status !== "skipped");

  return (
    <figure className="milestone-field">
      <svg viewBox={`0 0 ${W} 64`} role="group" aria-label="Milestones over time" className="milestone-svg">
        <line x1={PAD} x2={W - PAD} y1={30} y2={30} stroke="var(--hair-strong)" strokeWidth={1} />
        {ordered.map((m, i) => {
          const cx = x(m, i);
          const label = `${m.title}: ${stateWord(m.status)}`;
          return (
            <g key={m.id} role="img" aria-label={label} tabIndex={0} className="mark">
              <title>{label}</title>
              {isActive(m) && <rect x={cx - 9} y={21} width={18} height={18} fill="none" stroke="var(--cream)" strokeWidth={1} />}
              <rect
                x={cx - 5.5}
                y={24.5}
                width={11}
                height={11}
                fill={isDone(m) ? "var(--main)" : "none"}
                stroke={isDone(m) ? "var(--main)" : "var(--l1)"}
                strokeWidth={1}
                strokeDasharray={m.status === "skipped" ? "2 2" : undefined}
              />
              {next?.id === m.id && (
                <text x={cx} y={14} textAnchor="middle" className="mark-label">
                  {m.title.length > 28 ? `${m.title.slice(0, 27)}…` : m.title}
                </text>
              )}
            </g>
          );
        })}
        <text x={PAD} y={58} className="mark-label dim">
          {day(lo)}
        </text>
        <text x={W - PAD} y={58} textAnchor="end" className="mark-label dim">
          {day(hi)}
        </text>
      </svg>
    </figure>
  );
}
