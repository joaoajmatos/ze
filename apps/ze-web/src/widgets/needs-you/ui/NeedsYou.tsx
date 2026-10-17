import type { WsScreenRef } from "@myguyze/ze-client";
import { useNavigate } from "react-router-dom";
import { useAnswerGate } from "@/features/answer-gate";
import { HeldWriteCard, useConfirmation } from "@/features/respond-to-confirmation";
import type { PendingConfirm } from "@/features/respond-to-confirmation";
import { useLoopTransitionMutation } from "@/entities/loop";
import { useScreenPublisher } from "@/entities/screen-context";
import { askPath } from "@/shared/config";
import { ago } from "@/shared/lib";
import { ChatAboutChip, Module } from "@/shared/ui";
import type { Decision } from "../model/types";

interface Props {
  decisions: Decision[];
  loading: boolean;
  error: boolean;
  now: Date;
  offline: boolean;
  /** `<kind>:<id>` of the row to highlight, from `?focus=`. */
  focus: { kind: string; id: string } | null;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

function PendingConfirmRow({ pending, offline, focused }: { pending: PendingConfirm; offline: boolean; focused: boolean }) {
  const navigate = useNavigate();
  const { respond } = useConfirmation(false, pending.threadId);
  return (
    <div className={`row ${focused ? "focused" : ""}`}>
      <span className="t">{pending.title}</span>
      <span className="lbl">{pending.kind === "budget" ? "over budget" : "approve?"}</span>
      {pending.items.slice(0, 2).map((item) => (
        <span key={item.item_id} className="s">
          {item.effect_phrase}
        </span>
      ))}
      <span className="acts">
        <button type="button" className="ctl" disabled={offline || pending.submitted} onClick={() => respond(pending.id, "approve")}>
          Approve
        </button>
        <button type="button" className="ctl" disabled={offline || pending.submitted} onClick={() => respond(pending.id, "deny")}>
          Deny
        </button>
        <button type="button" className="ctl" onClick={() => navigate(askPath(pending.threadId))}>
          Open
        </button>
      </span>
    </div>
  );
}

/** Everything waiting on the user, each with its one or two actions. Cream, never coral. */
export function NeedsYou({ decisions, loading, error, now, offline, focus, onChatAbout }: Props) {
  const transition = useLoopTransitionMutation();
  const gateIds = decisions.filter((d) => d.kind === "gate").map((d) => d.id);
  const gate = useAnswerGate(gateIds);
  const isFocused = (kind: string, id: string) => focus?.kind === kind && focus.id === id;
  const refOf = (d: Decision): WsScreenRef | null =>
    d.kind === "held_write"
      ? ({ kind: "held_write", id: d.id } as WsScreenRef)
      : d.kind === "gate"
        ? ({ kind: "goal_gate", id: d.id, parent_id: d.goalId } as WsScreenRef)
        : d.kind === "suspected_loop"
          ? ({ kind: "loop", id: d.id } as WsScreenRef)
          : null;
  const chatChip = (d: Decision) => {
    const ref = refOf(d);
    return ref && onChatAbout ? <ChatAboutChip label={d.title} onClick={() => onChatAbout(ref, null)} /> : null;
  };

  useScreenPublisher({
    visible: decisions.map(refOf).filter((r): r is WsScreenRef => r !== null).slice(0, 10),
  });

  const busy = transition.isPending ? transition.variables?.loopId : null;

  return (
    <Module label="Needs you" tone={decisions.length ? "cream" : "default"} className="world-needs mod-needs">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read what is waiting on you.
        </p>
      ) : loading ? (
        <p className="muted">Reading…</p>
      ) : decisions.length === 0 ? (
        <p className="muted">Nothing waiting on you.</p>
      ) : (
        decisions.map((d) => {
          if (d.kind === "held_write") {
            return (
              <div key={`h${d.id}`} className="row">
                <HeldWriteCard held={d.held} disabled={offline} highlighted={isFocused("held_write", d.id)} />
                {chatChip(d)}
              </div>
            );
          }
          if (d.kind === "gate") {
            const state = gate.stateOf(d.id);
            const err = gate.errorOf(d.id);
            const inFlight = state === "in_flight";
            return (
              <div key={`g${d.id}`} className={`row ${isFocused("goal", d.goalId) ? "focused" : ""}`}>
                <span className="t">{d.title}</span>
                <span className="s">
                  Checkpoint · {d.goalTitle}
                  {d.at ? ` · waiting ${ago(d.at, now)}` : ""}
                </span>
                {state === "awaiting_instructions" && <span className="s">Waiting for your instructions</span>}
                <span className="acts">
                  <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.proceed(d.id)}>
                    Proceed
                  </button>
                  <button type="button" className="ctl" disabled={offline || inFlight} onClick={() => gate.stop(d.id)}>
                    Stop
                  </button>
                  <button
                    type="button"
                    className="ctl"
                    disabled={offline || inFlight}
                    onClick={() => {
                      if (gate.redirect(d.id)) onChatAbout?.({ kind: "goal_gate", id: d.id, parent_id: d.goalId } as WsScreenRef, null);
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
                {chatChip(d)}
              </div>
            );
          }
          if (d.kind === "suspected_loop") {
            const pending = busy === d.id;
            return (
              <div key={`l${d.id}`} className={`row dotted ${isFocused("loop", d.id) ? "focused" : ""}`}>
                <span className="t">{d.title}</span>
                <span className="lbl">confirm?</span>
                <span className="s">Suspected, not stated. Say so and I will keep track of it.</span>
                <span className="acts">
                  <button type="button" className="ctl" disabled={offline || pending} onClick={() => transition.mutate({ loopId: d.id, kind: "confirm" })}>
                    Yes, track it
                  </button>
                  <button type="button" className="ctl" disabled={offline || pending} onClick={() => transition.mutate({ loopId: d.id, kind: "drop" })}>
                    Drop
                  </button>
                </span>
                {chatChip(d)}
              </div>
            );
          }
          return <PendingConfirmRow key={`c${d.id}`} pending={d.pending} offline={offline} focused={false} />;
        })
      )}
      {transition.isError && (
        <p className="hot" role="alert">
          That didn't go through. Try again.
        </p>
      )}
      {offline && decisions.length > 0 && <p className="s">Ze is offline.</p>}
    </Module>
  );
}
