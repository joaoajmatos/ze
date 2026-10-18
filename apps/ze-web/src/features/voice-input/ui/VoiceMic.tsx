import { useEffect, useState } from "react";
import { useVoiceInput } from "../model/store";

const MAX_S = 115;
const WARN_S = 105;

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function Mic() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" aria-hidden="true">
      <rect x="5.5" y="1.5" width="5" height="8" rx="2.5" />
      <path d="M3 7.5a5 5 0 0 0 10 0M8 12.5v2" />
    </svg>
  );
}

function StopSquare() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <rect x="4" y="4" width="8" height="8" rx="1" />
    </svg>
  );
}

function Elapsed({ startedAt }: { startedAt: number | null }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const read = () => setSeconds(startedAt === null ? 0 : Math.floor((performance.now() - startedAt) / 1000));
    read();
    const id = setInterval(read, 250);
    return () => clearInterval(id);
  }, [startedAt]);
  const text = seconds >= WARN_S ? `${Math.max(0, MAX_S - seconds)}s left` : clock(seconds);
  return <span className="ml-1.5 font-mono text-[11px] tabular-nums">{text}</span>;
}

/** The Ask bar's mic. `blocked` is the bar's own reason when it cannot be used. */
export function VoiceMic({ blocked }: { blocked: string | null }) {
  const status = useVoiceInput((s) => s.status);
  const reason = useVoiceInput((s) => s.reason);
  const startedAt = useVoiceInput((s) => s.startedAt);
  const start = useVoiceInput((s) => s.start);
  const stop = useVoiceInput((s) => s.stop);
  const dismiss = useVoiceInput((s) => s.dismiss);

  const why = status === "unavailable" ? reason : blocked;
  if (why || status === "unavailable") {
    return (
      <button type="button" className="ctl" disabled aria-label={why ?? undefined} title={why ?? undefined}>
        <Mic />
      </button>
    );
  }
  if (status === "recording") {
    return (
      <button type="button" className="ctl" aria-pressed="true" aria-label="Stop recording" onClick={stop}>
        <StopSquare />
        <Elapsed startedAt={startedAt} />
      </button>
    );
  }
  if (status === "transcribing") {
    return (
      <button type="button" className="ctl" disabled aria-busy="true" aria-label="Transcribing">
        <Mic />
      </button>
    );
  }
  const label = "Speak to Ze (hold V)";
  return (
    <button
      type="button"
      className="ctl"
      aria-label={label}
      title={label}
      onClick={() => {
        if (status === "failed") dismiss();
        start();
      }}
    >
      <Mic />
    </button>
  );
}
