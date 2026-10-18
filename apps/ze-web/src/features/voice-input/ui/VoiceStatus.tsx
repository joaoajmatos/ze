import { useVoiceInput } from "../model/store";

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

  let body = null;
  if (status === "transcribing") {
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
            Record again
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
