import type { GateResponse, WsScreenRef } from "@myguyze/ze-client";
import { Link, useParams } from "react-router-dom";
import { MilestoneField } from "@/widgets/milestone-field";
import { useAnswerGate } from "@/features/answer-gate";
import { useChatAbout } from "@/features/ask-bar";
import { ReviewGoalLearning } from "@/features/review-goal-learning";
import { statusWord, TRACE_LIMIT, useGoalDetailQuery, useGoalTracesQuery, useStartGoalMutation } from "@/entities/goal";
import { useLoopsQuery } from "@/entities/loop";
import { useRemindersQuery } from "@/entities/reminder";
import { useScreenPublisher } from "@/entities/screen-context";
import { useWsStore } from "@/shared/api";
import { goalsPath } from "@/shared/config";
import { humanizeStatus, useSetBreadcrumbTitle } from "@/shared/lib";
import { ChatAboutChip, Chip, Module } from "@/shared/ui";

const CLAIM: Record<string, string> = { fact: "Fact", inference: "Inference (tentative)" };
const REMINDER_WORD = { upcoming: "upcoming", overdue: "overdue", fired: "fired" } as const;
const dateTime = (iso: string) => new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

function GateModule({ gate, goalId, goalTitle, gateApi, offline, onChatAbout }: { gate: GateResponse; goalId: string; goalTitle: string; gateApi: ReturnType<typeof useAnswerGate>; offline: boolean; onChatAbout: (ref: WsScreenRef, element?: Element | null) => void }) {
  const state = gateApi.stateOf(gate.id);
  const err = gateApi.errorOf(gate.id);
  const busy = state === "in_flight";
  const ref = { kind: "goal_gate", id: gate.id, parent_id: goalId } as WsScreenRef;
  return (
    <Module label="Needs you" tone="cream" className="gate-first">
      <div className="row">
        <span className="t">{gate.title}</span>
        <span className="s">
          Checkpoint · {goalTitle}
          {gate.fired_at ? ` · since ${dateTime(gate.fired_at)}` : ""}
        </span>
        {gate.plan_summary && <span className="s">{gate.plan_summary}</span>}
        {gate.context_summary && <span className="s">{gate.context_summary}</span>}
        {state === "awaiting_instructions" && <span className="s">Waiting for your instructions</span>}
        <span className="acts">
          <button type="button" className="ctl" disabled={offline || busy} onClick={() => gateApi.proceed(gate.id)}>
            Proceed
          </button>
          <button type="button" className="ctl" disabled={offline || busy} onClick={() => gateApi.stop(gate.id)}>
            Stop
          </button>
          <button type="button" className="ctl" disabled={offline || busy} onClick={() => gateApi.redirect(gate.id) && onChatAbout(ref, null)}>
            Redirect
          </button>
        </span>
        {err && (
          <p className="hot" role="alert">
            {err}
          </p>
        )}
        <ChatAboutChip label={gate.title} onClick={(chip) => onChatAbout(ref, chip.closest(".row"))} />
      </div>
    </Module>
  );
}

export function DoingGoalPage() {
  const { goalId = "" } = useParams<{ goalId: string }>();
  const detailQ = useGoalDetailQuery(goalId);
  const detail = detailQ.data;
  const traces = useGoalTracesQuery(goalId);
  const loops = useLoopsQuery();
  const reminders = useRemindersQuery({ status: "all" });
  const start = useStartGoalMutation();
  const chatAbout = useChatAbout();
  const offline = !useWsStore((s) => s.isConnected);

  const openGates = (detail?.gates ?? []).filter((g) => g.status === "awaiting_approval");
  const gateApi = useAnswerGate(openGates.map((g) => g.id));

  useSetBreadcrumbTitle(detail?.title);
  useScreenPublisher(
    detail
      ? {
          subject: [{ kind: "goal", id: detail.id, label: detail.title, component: "goal_module", as_of: detail.updated_at }],
          focused_module: "Goals",
        }
      : null,
  );

  if (detailQ.isLoading) {
    return (
      <p className="muted" role="status">
        Reading…
      </p>
    );
  }
  if (detailQ.isError || !detail) {
    return (
      <div className="doing-detail">
        <Link className="back-link" to={goalsPath()}>
          ← Doing
        </Link>
        <p className="hot" role="alert">
          Couldn't load this goal.
        </p>
        <button type="button" className="ctl" onClick={() => void detailQ.refetch()}>
          Retry
        </button>
      </div>
    );
  }

  const linked = (loops.data ?? []).filter((l) => l.goal_id === detail.id);
  const reminderOf = (id: string | null) => (id ? (reminders.data ?? []).find((r) => r.id === id) : undefined);
  const goalRef = { kind: "goal", id: detail.id, label: detail.title, component: "goal_module", as_of: detail.updated_at } as WsScreenRef;

  return (
    <div className="doing-detail">
      <Link className="back-link" to={goalsPath()}>
        ← Doing
      </Link>

      {detail.status === "awaiting_gate" && openGates.length === 0 && (
        <p className="s" role="status">
          This goal is waiting on a checkpoint, but the checkpoint isn't available.
        </p>
      )}
      {openGates.map((g) => (
        <GateModule key={g.id} gate={g} goalId={detail.id} goalTitle={detail.title} gateApi={gateApi} offline={offline} onChatAbout={chatAbout} />
      ))}

      <Module as="div" label="Goal" chatAboutLabel={detail.title} onChatAbout={(el) => chatAbout(goalRef, el)}>
        <h1 className="t">{detail.title}</h1>
        <p className="s">{detail.objective}</p>
        <p className="doing-detail-head">
          <Chip>{statusWord(detail.status)}</Chip>
          {detail.type && <Chip>{humanizeStatus(detail.type)}</Chip>}
          {detail.time_horizon && <Chip>{humanizeStatus(detail.time_horizon)}</Chip>}
        </p>
        {detail.status === "planning" && (
          <p className="acts">
            <button type="button" className="ctl" disabled={offline || start.isPending} onClick={() => start.mutate(detail.id)}>
              Start
            </button>
          </p>
        )}
        {start.isError && (
          <p className="hot" role="alert">
            That didn't go through. Try again.
          </p>
        )}
      </Module>

      <Module as="div" label="Milestones">
        <MilestoneField milestones={detail.milestones} />
      </Module>

      {(detail.retrospective_text || detail.learnings_summary) && (
        <Module as="div" label="Looking back">
          {detail.retrospective_text && <p>{detail.retrospective_text}</p>}
          {detail.learnings_summary && <p className="s">{detail.learnings_summary}</p>}
        </Module>
      )}

      <Module as="div" label="Learnings">
        {detail.learnings.length === 0 ? (
          <p className="muted">No learnings yet.</p>
        ) : (
          <ul className="doing-list">
            {detail.learnings.map((l) => (
              <li key={l.id} className="row">
                <span className="t">{l.content}</span>
                <span className="lbl">{CLAIM[l.claim_kind] ?? humanizeStatus(l.claim_kind)}</span>
                <span className="s">
                  {humanizeStatus(l.status)}
                  {l.evidence_count ? ` · ${l.evidence_count} ${l.evidence_count === 1 ? "piece" : "pieces"} of evidence` : ""}
                </span>
                <ReviewGoalLearning goalId={detail.id} learning={l} />
              </li>
            ))}
          </ul>
        )}
      </Module>

      <Module as="div" label="What it did">
        {traces.isError ? (
          <p className="hot" role="alert">
            Couldn't read what it did.
          </p>
        ) : traces.isLoading ? (
          <p className="muted" role="status">
            Reading…
          </p>
        ) : (traces.data ?? []).length === 0 ? (
          <p className="muted">No tool calls recorded.</p>
        ) : (
          <>
          {traces.data!.length >= TRACE_LIMIT && <p className="s">Showing the first {TRACE_LIMIT} tool calls.</p>}
          <ul className="trace-list">
            {traces.data!.map((t) => (
              <li key={t.id} className="row">
                <code className="t run-command">{t.tool_name}</code>
                <span className="lbl">{t.success ? "Worked" : "Failed"}</span>
                <span className="s">{t.duration_ms} ms</span>
                {!t.success && t.error && (
                  <details className="s">
                    <summary>What it reported</summary>
                    <pre className="run-output">{t.error}</pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
          </>
        )}
      </Module>

      <Module as="div" label="Open loops on this goal">
        {loops.isError ? (
          <p className="hot" role="alert">
            Couldn't read the loops.
          </p>
        ) : loops.isLoading ? (
          <p className="muted" role="status">
            Reading…
          </p>
        ) : linked.length === 0 ? (
          <p className="muted">Nothing open is linked to this goal.</p>
        ) : (
          <ul className="doing-list">
            {linked.map((l) => {
              const rem = reminderOf(l.reminder_id);
              return (
                <li key={l.id} className="row">
                  <span className="t">{l.title}</span>
                  <span className="lbl">{humanizeStatus(l.state)}</span>
                  {l.reminder_id && reminders.isError && <span className="s">Couldn't read reminders.</span>}
                  {rem && (
                    <span className="s">
                      Reminder · {rem.label} · {REMINDER_WORD[rem.status]} · {dateTime(rem.fire_at)}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Module>
    </div>
  );
}
