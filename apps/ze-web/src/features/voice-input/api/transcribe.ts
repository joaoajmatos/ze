import { transcribeVoice } from "@myguyze/ze-client";
import { extensionFor } from "../lib/mime";

export type VoiceErrorKind = "retryable" | "rerecord" | "unavailable";

export class VoiceError extends Error {
  constructor(
    readonly kind: VoiceErrorKind,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "VoiceError";
  }
}

const UNREADABLE = "I couldn't make out the recording.";

function serverLine(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof error === "object" && typeof detail === "string" && detail ? detail : null;
}

function failure(status: number | undefined, error: unknown): VoiceError {
  const line = serverLine(error);
  if (status === 413) return new VoiceError("rerecord", line ?? "The recording is too large. Record a shorter one.");
  if (status === 415) return new VoiceError("rerecord", line ?? "This recording format isn't supported.");
  if (status === 503) return new VoiceError("unavailable", line ?? "Voice input is not available on this server.");
  return new VoiceError("retryable", line ?? UNREADABLE);
}

/** Uploads one recording; throws a `VoiceError` the store turns into a status line. */
export async function transcribe(blob: Blob, mime: string): Promise<{ transcript: string; transcriptionId: string }> {
  const file = new File([blob], `recording.${extensionFor(mime)}`, { type: mime });
  let res;
  try {
    res = await transcribeVoice({ body: { file } });
  } catch {
    throw new VoiceError("retryable", UNREADABLE);
  }
  if (!res.data) throw failure(res.response?.status, res.error);
  return { transcript: res.data.transcript, transcriptionId: res.data.transcription_id };
}
