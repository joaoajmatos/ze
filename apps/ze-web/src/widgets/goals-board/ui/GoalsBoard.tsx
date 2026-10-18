import type { GoalListItem, WsScreenRef } from "@myguyze/ze-client";
import { Link } from "react-router-dom";
import type { AnswerGate } from "@/features/answer-gate";
import { boardOrder, goalRow, statusWord } from "@/entities/goal";
import { goalPath } from "@/shared/config";
import { ChatAboutChip, Meter, Module } from "@/shared/ui";

interface Props {
  goals: GoalListItem[];
  loading: boolean;
  error: boolean;
  offline: boolean;
  gate: AnswerGate;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

function GoalLine({ goal, offline, gate, onChatAbout }: { goal: GoalListItem } & Pick<Props, "offline" | "gate" | "onChatAbout">) {
  const row = goalRow(goal);
  const stuck = !!goal.stuck_since;
  const paused = goal.status === "paused";
  const state = gate.stateOf(goal.id);
  const err = gate.errorOf(goal.id);
  const inFlight = state === "in_flight";
  const ref = { kind: "goal", id: goal.id } as WsScreenRef;
  const openChat = () => onChatAbout?.(ref, null);

  return (
    <li className={`row ${stuck ? "hot" : ""}`} data-goal={goal.id}>
      <Link className="t goal-link" to={goalPath(goal.id)}>
        {goal.title}
      </Link>
      <span className="lbl">{stuck ? "Stuck" : statusWord(goal.status)}</span>
      {row.total > 0 && (
        <span className="s goal-meter">
          <Meter value={row.done / row.total} tone={stuck ? "hot" : "default"} label="milestones done" />
          <span className="ro">
            {row.done}/{row.total} milestones
          </span>
        </span>
      )}
      <span className="s">
        {row.next ? `Next: ${row.next} · ` : ""}
        {stuck
          ? `stuck since ${row.stuckSince}`
          : row.gateSince
            ? `gate open since ${row.gateSince}`
            : goal.status === "awaiting_gate" && !goal.gate_id
              ? "waiting on a checkpoint that isn't available"
              : `started ${row.age}`}
      </span>
      {stuck && (
        <span className="acts">
          <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.redirectStuck(goal.id) && openChat()}>
            Redirect
          </button>
          <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.pause(goal.id)}>
            Pause
          </button>
          {gate.abandonArmed(goal.id) ? (
            <>
              <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.abandon(goal.id)}>
                Yes, abandon
              </button>
              <button type="button" className="ctl" onClick={() => gate.disarmAbandon(goal.id)}>
                Keep it
              </button>
            </>
          ) : (
            <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.abandon(goal.id)}>
              Abandon
            </button>
          )}
        </span>
      )}
      {paused && onChatAbout && (
        <span className="acts">
          <button type="button" className="ctl" onClick={openChat}>
            Resume
          </button>
        </span>
      )}
      {err && (
        <p className="hot" role="alert">
          {err}
        </p>
      )}
      {onChatAbout && <ChatAboutChip label={goal.title} onClick={(chip) => onChatAbout(ref, chip.closest(".row"))} />}
    </li>
  );
}

/** One row per goal, read from the list alone. Coral only for a stuck goal. */
export function GoalsBoard({ goals, loading, error, offline, gate, onChatAbout }: Props) {
  const { live, paused, finished } = boardOrder(goals);
  const line = (g: GoalListItem) => <GoalLine key={g.id} goal={g} offline={offline} gate={gate} onChatAbout={onChatAbout} />;

  return (
    <Module label="Goals" className="doing-goals">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read your goals.
        </p>
      ) : loading ? (
        <p className="muted" role="status">
          Reading…
        </p>
      ) : goals.length === 0 ? (
        <p className="muted">No goals yet. Tell Ze what you want done over weeks and it will plan it.</p>
      ) : (
        <>
          <ul className="doing-list">{live.map(line)}</ul>
          {paused.length > 0 && <ul className="doing-list">{paused.map(line)}</ul>}
          {finished.length > 0 && (
            <details className="doing-finished">
              <summary className="lbl">Finished ({finished.length})</summary>
              <ul className="doing-list">{finished.map(line)}</ul>
            </details>
          )}
        </>
      )}
    </Module>
  );
}
