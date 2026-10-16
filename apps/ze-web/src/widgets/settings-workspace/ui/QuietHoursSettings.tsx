import { useEffect, useState } from "react";
import {
  useQuietHoursQuery,
  useUpdateQuietHoursMutation,
} from "@/entities/quiet-hours";
import { Button, Input } from "@/shared/ui";

const TIMEZONE_LIST_ID = "quiet-hours-timezones";

type ValidationDetail = { loc: (string | number)[]; msg: string };

function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";
  } catch {
    return "";
  }
}

function timeZoneOptions(): string[] {
  return (
    (Intl as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.(
      "timeZone",
    ) ?? []
  );
}

/** Maps FastAPI 422 `detail[]` entries to a field name → message map. */
function fieldMessages(error: unknown): Record<string, string> {
  const detail = (error as { detail?: ValidationDetail[] } | undefined)?.detail;
  if (!Array.isArray(detail)) return {};
  const out: Record<string, string> = {};
  for (const entry of detail) {
    const field = entry.loc[entry.loc.length - 1];
    if (typeof field === "string") out[field] = entry.msg;
  }
  return out;
}

export function QuietHoursSettings() {
  const { data } = useQuietHoursQuery();
  const mutation = useUpdateQuietHoursMutation();

  const [enabled, setEnabled] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [timezone, setTimezone] = useState(browserTimeZone());

  useEffect(() => {
    if (!data) return;
    setEnabled(data.enabled);
    setStart(data.start ?? "");
    setEnd(data.end ?? "");
    setTimezone(data.timezone ?? browserTimeZone());
  }, [data]);

  const errors = fieldMessages(mutation.error);
  const maxPerDay = data?.max_discretionary_per_day ?? 5;
  const status = data?.active_now
    ? `Quiet hours are on now · ${data.held_count} held`
    : "Quiet hours are off now";

  function handleSave() {
    mutation.mutate({
      enabled,
      start: start || null,
      end: end || null,
      timezone: timezone || null,
    });
  }

  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm text-foreground">
        <Input
          type="checkbox"
          aria-label="Quiet hours"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="h-4 w-4 p-0"
        />
        Quiet hours
      </label>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-smoke mb-1.5" htmlFor="quiet-start">
            Start
          </label>
          <Input
            id="quiet-start"
            type="time"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
          {errors.start && (
            <p className="text-xs text-destructive mt-1">{errors.start}</p>
          )}
        </div>
        <div>
          <label className="block text-xs text-smoke mb-1.5" htmlFor="quiet-end">
            End
          </label>
          <Input
            id="quiet-end"
            type="time"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
          {errors.end && (
            <p className="text-xs text-destructive mt-1">{errors.end}</p>
          )}
        </div>
      </div>

      <div>
        <label className="block text-xs text-smoke mb-1.5" htmlFor="quiet-tz">
          Timezone
        </label>
        <Input
          id="quiet-tz"
          list={TIMEZONE_LIST_ID}
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
        />
        <datalist id={TIMEZONE_LIST_ID}>
          {timeZoneOptions().map((zone) => (
            <option key={zone} value={zone} />
          ))}
        </datalist>
        {errors.timezone && (
          <p className="text-xs text-destructive mt-1">{errors.timezone}</p>
        )}
      </div>

      <p className="text-xs text-smoke leading-relaxed">
        Ze sends at most {maxPerDay} unprompted nudges a day. Reminders you set always come
        through.
      </p>
      <p className="text-xs text-smoke">{status}</p>

      <Button onClick={handleSave} disabled={mutation.isPending} className="w-full">
        {mutation.isPending ? "Saving…" : "Save"}
      </Button>
    </div>
  );
}
