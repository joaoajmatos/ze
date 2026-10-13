import type { RollbackRecordResponse } from "@myguyze/ze-client";

interface RollbackNoticeProps {
  rollback: RollbackRecordResponse | null | undefined;
}

function joinPhrases(phrases: string[]): string {
  if (phrases.length <= 1) return phrases[0] ?? "";
  return `${phrases.slice(0, -1).join(", ")} and ${phrases.at(-1)}`;
}

export function rollbackNoticeText(rollback: RollbackRecordResponse): string | null {
  const undone = joinPhrases(
    (rollback.entries ?? []).filter((e) => e.outcome === "undone").map((e) => e.effect_phrase),
  );
  const failed = joinPhrases(
    (rollback.entries ?? []).filter((e) => e.outcome !== "undone").map((e) => e.effect_phrase),
  );
  switch (rollback.state) {
    case "partial":
      return `Ze undid ${undone || "nothing"}, but could not undo ${failed}.`;
    case "rolled_back_retry_failed":
      return `Ze undid ${undone} but could not write a new reply.`;
    case "rolled_back_awaiting_confirmation":
      return `Ze undid ${undone} and is waiting for your confirmation.`;
    default:
      return null;
  }
}

export function RollbackNotice({ rollback }: RollbackNoticeProps) {
  const text = rollback ? rollbackNoticeText(rollback) : null;
  if (!text) return null;
  return (
    <p role="status" data-testid="rollback-notice" className="px-1 text-[11px] text-smoke">
      {text}
    </p>
  );
}
