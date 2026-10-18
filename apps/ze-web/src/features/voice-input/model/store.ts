import { create } from "zustand";
import { presenceActions } from "@/entities/presence";
import { transcribe, VoiceError } from "../api/transcribe";
import { pickMime } from "../lib/mime";
import { recorderLevel, startRecorder, type Recorder } from "../lib/recorder";

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

/** The server refuses over two minutes; stop with margin. */
const MAX_RECORDING_MS = 115_000;
const TICK_MS = 250;
const NOTICE_MS = 6000;

let recorder: Recorder | null = null;
let mime = "";
let ticker: ReturnType<typeof setInterval> | null = null;
let noticeTimer: ReturnType<typeof setTimeout> | null = null;
/** Set when stop or dismiss arrives while the microphone is still opening. */
let cancelPending: "stop" | "discard" | null = null;
let onTranscript: ((text: string, transcriptionId: string) => void) | null = null;

function clearTicker() {
  if (ticker) clearInterval(ticker);
  ticker = null;
}

function clearNotice() {
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = null;
}

function startFailure(err: unknown): string {
  const name = (err as { name?: string } | null)?.name;
  if (name === "NotAllowedError") return "Microphone access is blocked. Allow it in the browser's site settings.";
  if (name === "NotFoundError") return "No microphone found.";
  return "This browser can't record audio.";
}

export const useVoiceInput = create<VoiceInputState>((set, get) => {
  const unavailable = (reason: string) => {
    presenceActions.voice("none");
    set({ status: "unavailable", reason, startedAt: null, failure: null });
  };

  const upload = async () => {
    const pending = get().pending;
    if (!pending) return;
    set({ status: "transcribing", failure: null });
    presenceActions.voice("transcribing");
    try {
      const { transcript, transcriptionId } = await transcribe(pending.blob, pending.mime);
      presenceActions.voice("none");
      if (!transcript.trim()) {
        set({ status: "idle", pending: null, notice: "heard_nothing" });
        clearNotice();
        noticeTimer = setTimeout(() => set({ notice: null }), NOTICE_MS);
        return;
      }
      set({ status: "idle", pending: null });
      deliverTranscript(transcript, transcriptionId);
    } catch (err) {
      presenceActions.voice("none");
      const e = err instanceof VoiceError ? err : new VoiceError("retryable", "I couldn't make out the recording.");
      if (e.kind === "unavailable") return unavailable(e.detail);
      set({ status: "failed", failure: { kind: e.kind, detail: e.detail }, pending: e.kind === "retryable" ? pending : null });
    }
  };

  const finish = async (discard: boolean) => {
    const rec = recorder;
    recorder = null;
    clearTicker();
    if (!rec) return;
    const blob = await rec.stop();
    if (discard) return;
    set({ pending: { blob, mime }, startedAt: null });
    await upload();
  };

  return {
    status: "idle",
    startedAt: null,
    reason: null,
    failure: null,
    notice: null,
    pending: null,

    start: () => {
      if (get().status !== "idle") return;
      clearNotice();
      const supported = typeof MediaRecorder !== "undefined" ? pickMime((m) => MediaRecorder.isTypeSupported(m)) : null;
      if (!navigator.mediaDevices) return unavailable("No microphone found.");
      if (!supported) return unavailable("This browser can't record audio.");
      mime = supported;
      cancelPending = null;
      set({ status: "recording", startedAt: null, notice: null, failure: null, pending: null });
      presenceActions.voice("recording");
      startRecorder({ mime: supported }).then(
        (rec) => {
          recorder = rec;
          if (cancelPending) {
            const discard = cancelPending === "discard";
            cancelPending = null;
            if (discard) set({ status: "idle", startedAt: null });
            void finish(discard);
            return;
          }
          const began = performance.now();
          set({ startedAt: began });
          ticker = setInterval(() => {
            if (performance.now() - began >= MAX_RECORDING_MS) get().stop();
          }, TICK_MS);
        },
        (err) => unavailable(startFailure(err)),
      );
    },

    stop: () => {
      if (get().status !== "recording") return;
      if (!recorder) {
        cancelPending = "stop";
        set({ status: "transcribing", startedAt: null });
        presenceActions.voice("transcribing");
        return;
      }
      set({ status: "transcribing", startedAt: null });
      presenceActions.voice("transcribing");
      void finish(false);
    },

    retry: () => {
      const { status, failure, pending } = get();
      if (status !== "failed" || failure?.kind !== "retryable" || !pending) return;
      void upload();
    },

    dismiss: () => {
      clearNotice();
      if (get().status === "recording") {
        presenceActions.voice("none");
        if (!recorder) cancelPending = "discard";
        set({ status: "idle", startedAt: null, pending: null, failure: null, notice: null });
        if (recorder) void finish(true);
        return;
      }
      if (get().status === "transcribing") return;
      set({ status: get().status === "unavailable" ? "unavailable" : "idle", pending: null, failure: null, notice: null });
    },
  };
});

/** The shell registers where a transcript goes; the returned function unregisters it. */
export function registerTranscript(cb: (text: string, transcriptionId: string) => void): () => void {
  onTranscript = cb;
  return () => {
    if (onTranscript === cb) onTranscript = null;
  };
}

/** The input level 0..1 for the orb; 0 unless recording. */
export function currentLevel(): number {
  return useVoiceInput.getState().status === "recording" ? recorderLevel() : 0;
}

/** Delivers a transcript to the registered callback. */
export function deliverTranscript(text: string, transcriptionId: string): void {
  onTranscript?.(text, transcriptionId);
}
