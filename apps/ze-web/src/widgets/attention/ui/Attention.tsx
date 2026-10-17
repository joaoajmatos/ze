import { useState } from "react";
import { useAttentionBudgetQuery, useNotificationOutcomesQuery } from "@/entities/notification";
import { useQuietHoursQuery, useUpdateQuietHoursMutation } from "@/entities/quiet-hours";
import { Dots, Module } from "@/shared/ui/hud";
import { fieldMessages } from "../lib/field-messages";
import { browserTimeZone, timeZoneOptions } from "../lib/timezone";

const TIMEZONE_LIST_ID = "gov-quiet-timezones";

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

function Budget() {
  const budget = useAttentionBudgetQuery();
  if (budget.isError) {
    return (
      <p className="gov-err">
        Could not load the push budget.{" "}
        <button type="button" className="ctl-text" onClick={() => void budget.refetch()}>
          Retry
        </button>
      </p>
    );
  }
  if (!budget.data) return <p className="gov-note">Loading the push budget…</p>;
  const { used, max_per_day, next_slot_at, held_count } = budget.data;
  return (
    <div className="gov-figure">
      <Dots max={max_per_day} lit={Math.min(used, max_per_day)} label={`${used} of ${max_per_day} pushes used in the last 24 hours`} />
      <span className="ro">
        {used}/{max_per_day}
      </span>
      {next_slot_at && <span className="ro">next slot {clock(next_slot_at)}</span>}
      <span className="ro">{held_count} held</span>
    </div>
  );
}

function Outcomes() {
  const outcomes = useNotificationOutcomesQuery();
  if (outcomes.isError) return <p className="gov-err">Could not load recent push outcomes.</p>;
  if (!outcomes.data || outcomes.data.length === 0) return null;
  return (
    <ul aria-label="Recent push outcomes" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {outcomes.data.map((n) => (
        <li key={n.id} className={`row gov-row${n.delivery === "failed" ? " hot" : ""}`}>
          <span className="t">{n.title}</span>
          <span className="ro">{n.delivery}</span>
          <span className="s">{new Date(n.created_at).toLocaleString()}</span>
        </li>
      ))}
    </ul>
  );
}

/** Governance › Attention: how Ze may interrupt, what it has spent and what it held back. */
export function Attention() {
  const { data } = useQuietHoursQuery();
  const mutation = useUpdateQuietHoursMutation();
  const [enabled, setEnabled] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [timezone, setTimezone] = useState(browserTimeZone());
  const [problem, setProblem] = useState<string | null>(null);
  const [syncedData, setSyncedData] = useState<typeof data>(undefined);
  if (data && data !== syncedData) {
    setSyncedData(data);
    setEnabled(data.enabled);
    setStart(data.start ?? "");
    setEnd(data.end ?? "");
    setTimezone(data.timezone ?? browserTimeZone());
  }

  const errors = fieldMessages(mutation.error);

  function save() {
    if (enabled) {
      if (!start || !end) return setProblem("Set a start and an end.");
      if (start === end) return setProblem("Start and end must differ.");
      if (!timezone) return setProblem("Choose a timezone.");
    }
    setProblem(null);
    mutation.mutate({ enabled, start: enabled ? start : null, end: enabled ? end : null, timezone: timezone || null });
  }

  return (
    <Module label="What can interrupt me?">
      <div className="gov-stack">
        <Budget />
        <Outcomes />
        <p className="gov-note">
          Pushes go to your ntfy topic. Reminders you set always come through.{" "}
          <a className="key" href="https://ntfy.sh" target="_blank" rel="noreferrer">
            Open ntfy
          </a>
        </p>

        <label className="gov-check">
          <input type="checkbox" aria-label="Quiet hours" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Quiet hours{data?.active_now ? " (on now)" : ""}
        </label>
        <div className="gov-pair">
          <div className="gov-field">
            <label className="lbl" htmlFor="gov-quiet-start">
              Start
            </label>
            <input id="gov-quiet-start" className="gov-in" type="time" value={start} onChange={(e) => setStart(e.target.value)} aria-invalid={Boolean(errors.start)} />
            {errors.start && <p className="gov-err">{errors.start}</p>}
          </div>
          <div className="gov-field">
            <label className="lbl" htmlFor="gov-quiet-end">
              End
            </label>
            <input id="gov-quiet-end" className="gov-in" type="time" value={end} onChange={(e) => setEnd(e.target.value)} aria-invalid={Boolean(errors.end)} />
            {errors.end && <p className="gov-err">{errors.end}</p>}
          </div>
        </div>
        <div className="gov-field">
          <label className="lbl" htmlFor="gov-quiet-tz">
            Timezone
          </label>
          <input id="gov-quiet-tz" className="gov-in" list={TIMEZONE_LIST_ID} value={timezone} onChange={(e) => setTimezone(e.target.value)} aria-invalid={Boolean(errors.timezone)} />
          <datalist id={TIMEZONE_LIST_ID}>
            {timeZoneOptions().map((zone) => (
              <option key={zone} value={zone} />
            ))}
          </datalist>
          {errors.timezone && <p className="gov-err">{errors.timezone}</p>}
        </div>
        {problem && <p className="gov-err">{problem}</p>}
        <div>
          <button type="button" className="ctl primary" onClick={save} disabled={mutation.isPending}>
            {mutation.isPending ? "Saving" : mutation.isSuccess ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </Module>
  );
}
