import type { GoalListItem, HeldWriteOut, WsScreenRef } from "@myguyze/ze-client";
import type { AnswerGate } from "@/features/answer-gate";
import { HeldWriteCard } from "@/features/respond-to-confirmation";
import { useStartGoalMutation } from "@/entities/goal";
import { ago } from "@/shared/lib";
import { ChatAboutChip, Module } from "@/shared/ui";

interface Props {
  goals: GoalListItem[];
  held: HeldWriteOut[];
  loading: boolean;
  error: boolean;
  now: Date;
  offline: boolean;
  gate: AnswerGate;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

/** Everything in Doing that waits on the user: plans to start, checkpoints, held writes. Cream, never coral. */
export function DoingNeedsYou({ goals, held, loading, error, now, offline, gate, onChatAbout }: Props) {
  const start = useStartGoalMutation();
  const planning = goals.filter((g) => g.status === "planning");
  const gates = goals.filter((g) => g.gate_id);
  const count = planning.length + gates.length + held.length;
  const chat = (label: string, ref: WsScreenRef) =>
    onChatAbout ? <ChatAboutChip label={label} onClick={(chip) => onChatAbout(ref, chip.closest(".row"))} /> : null;

  return (
    <Module label="Needs you" tone={count ? "cream" : "default"} className="doing-needs">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read what is waiting on you.
        </p>
      ) : loading ? (
        <p className="muted" role="status">
          Reading…
        </p>
      ) : count === 0 ? (
        <p className="muted">Nothing needs you.</p>
      ) : (
        <>
          {planning.map((g) => (
            <div key={`p${g.id}`} className="row">
              <span className="t">{g.title}</span>
              <span className="lbl">plan ready</span>
              <span className="acts">
                <button type="button" className="ctl" disabled={offline || (start.isPending && start.variables === g.id)} onClick={() => start.mutate(g.id)}>
                  Start
                </button>
              </span>
              {chat(g.title, { kind: "goal", id: g.id, label: g.title } as WsScreenRef)}
            </div>
          ))}
          {gates.map((g) => {
            const id = g.gate_id!;
            const state = gate.stateOf(id);
            const err = gate.errorOf(id);
            const inFlight = state === "in_flight";
            return (
              <div key={`g${id}`} className="row">
                <span className="t">{g.gate_title ?? "Checkpoint"}</span>
                <span className="s">
                  Checkpoint · {g.title}
                  {g.gate_open_since ? ` · waiting ${ago(new Date(g.gate_open_since), now)}` : ""}
                </span>
                {state === "awaiting_instructions" && <span className="s">Waiting for your instructions</span>}
                <span className="acts">
                  <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.proceed(id)}>
                    Proceed
                  </button>
                  <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.stop(id)}>
                    Stop
                  </button>
                  <button
                    type="button"
                    className="ctl"
                    disabled={offline || inFlight}
                    onClick={() => {
                      if (gate.redirect(id)) onChatAbout?.({ kind: "goal_gate", id, parent_id: g.id, label: g.gate_title ?? g.title } as WsScreenRef, null);
                    }}
                  >
                    Redirect
                  </button>
                </span>
                {err && (
                  <p className="hot" role="alert">
                    {err}
                  </p>
                )}
                {chat(g.gate_title ?? g.title, { kind: "goal_gate", id, parent_id: g.id, label: g.gate_title ?? g.title } as WsScreenRef)}
              </div>
            );
          })}
          {held.map((h) => (
            <div key={`h${h.request_id}`} className="row">
              <HeldWriteCard held={h} disabled={offline} />
              {chat(h.source_name, { kind: "held_write", id: h.request_id, label: h.source_name } as WsScreenRef)}
            </div>
          ))}
        </>
      )}
      {start.isError && (
        <p className="hot" role="alert">
          That didn't go through. Try again.
        </p>
      )}
      {offline && count > 0 && <p className="s">Ze is offline.</p>}
    </Module>
  );
}
