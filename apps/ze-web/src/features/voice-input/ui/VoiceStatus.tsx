import { useEffect, useState } from "react";
import { useVoiceInput } from "../model/store";

const WARN_MS = 105_000;

const LINE_BUTTON =
  "inline-flex min-h-11 items-center px-3 font-mono text-[11px] uppercase tracking-wide text-smoke hover:text-white focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-2";

/** The voice status line above the Ask bar. */
export function VoiceStatus() {
  const status = useVoiceInput((s) => s.status);
  const failure = useVoiceInput((s) => s.failure);
  const notice = useVoiceInput((s) => s.notice);
  const start = useVoiceInput((s) => s.start);
  const retry = useVoiceInput((s) => s.retry);
  const dismiss = useVoiceInput((s) => s.dismiss);
  const startedAt = useVoiceInput((s) => s.startedAt);

  // The mic button counts down for the eyes; this line says it once for a screen reader.
  const [warnedFor, setWarnedFor] = useState<number | null>(null);
  useEffect(() => {
    if (status !== "recording" || startedAt === null) return;
    const id = setInterval(() => setWarnedFor(performance.now() - startedAt >= WARN_MS ? startedAt : null), 250);
    return () => clearInterval(id);
  }, [status, startedAt]);
  const warned = status === "recording" && startedAt !== null && warnedFor === startedAt;

  let body = null;
  if (status === "recording" && warned) {
    body = <span>10 seconds left</span>;
  } else if (status === "transcribing") {
    body = <span>Transcribing…</span>;
  } else if (status === "failed" && failure) {
    body = (
      <>
        <span>{failure.detail}</span>
        {failure.kind === "retryable" ? (
          <button type="button" className={LINE_BUTTON} onClick={retry}>
            Retry
          </button>
        ) : (
          <button
            type="button"
            className={LINE_BUTTON}
            onClick={() => {
              dismiss();
              start();
            }}
          >
            {failure.kind === "device" ? "Try again" : "Record again"}
          </button>
        )}
        <button type="button" className={LINE_BUTTON} onClick={dismiss}>
          Dismiss
        </button>
      </>
    );
  } else if (notice === "heard_nothing") {
    body = <span>Ze heard nothing</span>;
  }

  return (
    <p className="voice-status flex flex-wrap items-center gap-x-2 font-mono text-[11px] text-smoke" role="status" aria-live="polite">
      {body}
    </p>
  );
}
