import type { GoalListItem, LoopListItem, WorkflowResponse } from "@myguyze/ze-client";
import { agoPhrase, stateWords } from "@/shared/lib";
import { Module } from "@/shared/ui";

interface Props {
  /** Open loops plus closed ones; the window is applied here. */
  loops: LoopListItem[];
  closedLoops: LoopListItem[];
  goals: GoalListItem[];
  workflows: WorkflowResponse[];
  loading: boolean;
  error: boolean;
  now: Date;
}

const WEEK = 7 * 86_400_000;

interface Touch {
  key: string;
  kind: "loop" | "goal" | "workflow";
  title: string;
  state: string;
  at: Date;
}

/** Loops, goals and workflows changed in the last seven days. `listLoops` has no `since`, so the window is applied here. */
export function Touched({ loops, closedLoops, goals, workflows, loading, error, now }: Props) {
  const within = (iso: string | null | undefined): Date | null => {
    if (!iso) return null;
    const d = new Date(iso);
    return now.getTime() - d.getTime() <= WEEK ? d : null;
  };
  const touches: Touch[] = [];
  for (const l of [...loops, ...closedLoops]) {
    const at = within(l.updated_at);
    if (at) touches.push({ key: `l${l.id}`, kind: "loop", title: l.title, state: stateWords("loop", l.state), at });
  }
  for (const g of goals) {
    const at = within(g.last_progress_at);
    if (at) touches.push({ key: `g${g.id}`, kind: "goal", title: g.title, state: stateWords("goal", g.status), at });
  }
  for (const w of workflows) {
    const at = within(w.last_run_at);
    if (at) touches.push({ key: `w${w.id}`, kind: "workflow", title: w.name, state: "ran", at });
  }
  touches.sort((a, b) => b.at.getTime() - a.at.getTime());

  return (
    <Module label="Touched · 7 d" className="world-touched">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read what changed.
        </p>
      ) : loading ? (
        <p className="muted">Reading…</p>
      ) : touches.length === 0 ? (
        <p className="muted">Nothing changed this week.</p>
      ) : (
        touches.slice(0, 8).map((t) => (
          <div key={t.key} className="row">
            <span className="t">{t.title}</span>
            <span className="ro">{agoPhrase(t.at, now)}</span>
            <span className="s">
              {t.kind} · {t.state}
            </span>
          </div>
        ))
      )}
    </Module>
  );
}
