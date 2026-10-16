import type { RollbackRecordResponse } from "@myguyze/ze-client";

interface RollbackNoticeProps {
  rollback: RollbackRecordResponse | null | undefined;
  /** The server still reports the thread busy: a regeneration may be in flight. */
  busy?: boolean;
}

function joinPhrases(phrases: string[]): string {
  if (phrases.length <= 1) return phrases[0] ?? "";
  return `${phrases.slice(0, -1).join(", ")} and ${phrases.at(-1)}`;
}

function rollbackNoticeText(rollback: RollbackRecordResponse): string | null {
  const undone = joinPhrases(
    (rollback.entries ?? []).filter((e) => e.outcome === "undone").map((e) => e.effect_phrase),
  );
  const failed = joinPhrases(
    (rollback.entries ?? []).filter((e) => e.outcome === "failed").map((e) => e.effect_phrase),
  );
  const skipped = joinPhrases(
    (rollback.entries ?? []).filter((e) => e.outcome === "not_attempted").map((e) => e.effect_phrase),
  );
  switch (rollback.state) {
    case "partial":
      return (
        `Ze undid ${undone || "nothing"}, but could not undo ${failed || "everything"}.` +
        (skipped ? ` It did not try ${skipped}.` : "")
      );
    case "rolled_back_retry_failed":
      return `Ze undid ${undone} but could not write a new reply.`;
    case "rolled_back_awaiting_confirmation":
      return `Ze undid ${undone} and is waiting for your confirmation.`;
    default:
      return null;
  }
}

const IN_FLIGHT_STATES = new Set(["rolled_back_retry_failed", "rolled_back_awaiting_confirmation"]);

export function RollbackNotice({ rollback, busy }: RollbackNoticeProps) {
  const inFlight = busy && rollback && IN_FLIGHT_STATES.has(rollback.state);
  const text = rollback && !inFlight ? rollbackNoticeText(rollback) : null;
  if (!text) return null;
  return (
    <p role="status" data-testid="rollback-notice" className="px-1 text-[11px] text-smoke">
      {text}
    </p>
  );
}
