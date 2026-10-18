import { create } from "zustand";

export type VoiceStatus = "idle" | "recording" | "transcribing" | "failed" | "unavailable";

export interface VoiceFailure {
  kind: "retryable" | "rerecord";
  detail: string;
}

export interface VoiceInputState {
  status: VoiceStatus;
  /** `performance.now()` stamp of the moment recording began. */
  startedAt: number | null;
  /** Why the mic is unavailable, in a plain line. */
  reason: string | null;
  failure: VoiceFailure | null;
  notice: "heard_nothing" | null;
  pending: { blob: Blob; mime: string } | null;
  start: () => void;
  stop: () => void;
  retry: () => void;
  dismiss: () => void;
}

const noop = () => {};

export const useVoiceInput = create<VoiceInputState>(() => ({
  status: "idle",
  startedAt: null,
  reason: null,
  failure: null,
  notice: null,
  pending: null,
  start: noop,
  stop: noop,
  retry: noop,
  dismiss: noop,
}));

let onTranscript: ((text: string, transcriptionId: string) => void) | null = null;

/** The shell registers where a transcript goes; the returned function unregisters it. */
export function registerTranscript(cb: (text: string, transcriptionId: string) => void): () => void {
  onTranscript = cb;
  return () => {
    if (onTranscript === cb) onTranscript = null;
  };
}

/** The input level 0..1 for the orb; 0 unless recording. */
export function currentLevel(): number {
  return 0;
}

/** Delivers a transcript to the registered callback. */
export function deliverTranscript(text: string, transcriptionId: string): void {
  onTranscript?.(text, transcriptionId);
}
