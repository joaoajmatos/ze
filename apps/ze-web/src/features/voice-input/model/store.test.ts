import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  startRecorder: vi.fn(),
  recorderLevel: vi.fn(() => 0),
  transcribe: vi.fn(),
  voice: vi.fn(),
}));
vi.mock("../lib/recorder", () => ({ startRecorder: m.startRecorder, recorderLevel: m.recorderLevel }));
vi.mock("../api/transcribe", async () => {
  const actual = await vi.importActual<typeof import("../api/transcribe")>("../api/transcribe");
  return { ...actual, transcribe: m.transcribe };
});
vi.mock("@/entities/presence", () => ({ presenceActions: { voice: m.voice } }));
import { VoiceError } from "../api/transcribe";
import { currentLevel, registerTranscript, useVoiceInput } from "./store";

const BLOB = new Blob(["a"]);
const s = () => useVoiceInput.getState();
let stop: ReturnType<typeof vi.fn>;
let got: Array<[string, string]>;
let unregister: () => void;

class FakeMediaRecorder {
  static isTypeSupported = () => true;
}

const flush = () => vi.advanceTimersByTimeAsync(0);

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {} });
  stop = vi.fn(async () => BLOB);
  m.startRecorder.mockReset().mockResolvedValue({ stop });
  m.transcribe.mockReset().mockResolvedValue({ transcript: "hello", transcriptionId: "t1" });
  m.voice.mockReset();
  m.recorderLevel.mockReset().mockReturnValue(0);
  got = [];
  unregister = registerTranscript((t, id) => got.push([t, id]));
  s().dismiss();
  useVoiceInput.setState({ status: "idle", reason: null, failure: null, notice: null, pending: null, startedAt: null });
});
afterEach(() => {
  unregister();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function record() {
  s().start();
  await flush();
}
async function recordAndStop() {
  await record();
  s().stop();
  await flush();
}

describe("record and transcribe", () => {
  it("start records, stop transcribes and delivers", async () => {
    await record();
    expect(s().status).toBe("recording");
    expect(m.voice).toHaveBeenLastCalledWith("recording");
    s().stop();
    expect(s().status).toBe("transcribing");
    expect(m.voice).toHaveBeenLastCalledWith("transcribing");
    await flush();
    expect(got).toEqual([["hello", "t1"]]);
    expect(s().status).toBe("idle");
    expect(m.voice).toHaveBeenLastCalledWith("none");
    expect(s().pending).toBeNull();
  });

  it("start while transcribing does nothing", async () => {
    m.transcribe.mockReturnValue(new Promise(() => {}));
    await recordAndStop();
    s().start();
    await flush();
    expect(m.startRecorder).toHaveBeenCalledTimes(1);
    expect(s().status).toBe("transcribing");
  });

  it("dismiss while recording discards the recording", async () => {
    await record();
    s().dismiss();
    await flush();
    expect(stop).toHaveBeenCalled();
    expect(m.transcribe).not.toHaveBeenCalled();
    expect(s().status).toBe("idle");
    expect(s().pending).toBeNull();
  });
});

describe("the 115 s budget", () => {
  it("counts from when recording began, not from start()", async () => {
    let resolve!: (r: unknown) => void;
    m.startRecorder.mockReturnValue(new Promise((r) => (resolve = r)));
    s().start();
    await vi.advanceTimersByTimeAsync(5000);
    resolve({ stop });
    await flush();
    await vi.advanceTimersByTimeAsync(114_000);
    expect(s().status).toBe("recording");
    await vi.advanceTimersByTimeAsync(1_500);
    expect(m.transcribe).toHaveBeenCalledTimes(1);
  });

  it("stops at the first tick past 115 s of elapsed time, even when ticks were throttled", async () => {
    await record();
    const base = performance.now();
    const spy = vi.spyOn(performance, "now").mockReturnValue(base + 130_000);
    await vi.advanceTimersByTimeAsync(250);
    expect(m.transcribe).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });
});

describe("currentLevel", () => {
  it("is 0 unless recording, whatever the module ref holds", async () => {
    m.recorderLevel.mockReturnValue(0.7);
    expect(currentLevel()).toBe(0);
    await record();
    expect(currentLevel()).toBe(0.7);
    s().stop();
    expect(currentLevel()).toBe(0);
  });
});

describe("empty transcript", () => {
  it("sets a notice, calls no callback, and clears after 6 s or at the next start", async () => {
    m.transcribe.mockResolvedValue({ transcript: "  \n", transcriptionId: "t2" });
    await recordAndStop();
    expect(got).toEqual([]);
    expect(s().notice).toBe("heard_nothing");
    await vi.advanceTimersByTimeAsync(6000);
    expect(s().notice).toBeNull();

    await recordAndStop();
    expect(s().notice).toBe("heard_nothing");
    s().start();
    expect(s().notice).toBeNull();
  });
});

describe("failures", () => {
  it("retryable keeps the blob and retry re-uploads the same one", async () => {
    m.transcribe.mockRejectedValueOnce(new VoiceError("retryable", "Server line."));
    await recordAndStop();
    expect(s().status).toBe("failed");
    expect(s().failure).toEqual({ kind: "retryable", detail: "Server line." });
    expect(s().pending?.blob).toBe(BLOB);
    s().retry();
    expect(s().status).toBe("transcribing");
    await flush();
    expect(m.startRecorder).toHaveBeenCalledTimes(1);
    expect(m.transcribe).toHaveBeenCalledTimes(2);
    expect(m.transcribe.mock.calls[1][0]).toBe(BLOB);
    expect(got).toEqual([["hello", "t1"]]);
  });

  it("rerecord offers no retry", async () => {
    m.transcribe.mockRejectedValueOnce(new VoiceError("rerecord", "Too long."));
    await recordAndStop();
    expect(s().failure).toEqual({ kind: "rerecord", detail: "Too long." });
    s().retry();
    await flush();
    expect(m.transcribe).toHaveBeenCalledTimes(1);
    expect(s().status).toBe("failed");
  });

  it("dismiss clears a failure and the pending recording", async () => {
    m.transcribe.mockRejectedValueOnce(new VoiceError("retryable", "x"));
    await recordAndStop();
    s().dismiss();
    expect(s().status).toBe("idle");
    expect(s().pending).toBeNull();
    expect(s().failure).toBeNull();
  });

  it("503 makes voice unavailable with the server's line", async () => {
    m.transcribe.mockRejectedValueOnce(new VoiceError("unavailable", "Voice input is not available on this server."));
    await recordAndStop();
    expect(s().status).toBe("unavailable");
    expect(s().reason).toBe("Voice input is not available on this server.");
  });
});

describe("start failures", () => {
  const unavailable = async (line: string) => {
    expect(s().status).toBe("unavailable");
    expect(s().reason).toBe(line);
    expect(m.voice).toHaveBeenLastCalledWith("none");
  };

  it("a blocked microphone", async () => {
    m.startRecorder.mockRejectedValue(Object.assign(new Error("no"), { name: "NotAllowedError" }));
    await record();
    await unavailable("Microphone access is blocked. Allow it in the browser's site settings.");
  });

  it("no microphone", async () => {
    m.startRecorder.mockRejectedValue(Object.assign(new Error("no"), { name: "NotFoundError" }));
    await record();
    await unavailable("No microphone found.");
  });

  it("no mediaDevices", async () => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
    await record();
    await unavailable("No microphone found.");
  });

  it("no MediaRecorder or no supported mime", async () => {
    vi.stubGlobal("MediaRecorder", undefined);
    await record();
    await unavailable("This browser can't record audio.");
  });

  it("an unsupported mime", async () => {
    vi.stubGlobal("MediaRecorder", { isTypeSupported: () => false });
    await record();
    await unavailable("This browser can't record audio.");
  });
});
