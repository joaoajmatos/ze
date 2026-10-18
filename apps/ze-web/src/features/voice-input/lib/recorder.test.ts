import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { recorderLevel, startRecorder } from "./recorder";

class FakeRecorder {
  static last: FakeRecorder;
  state = "inactive";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  startArgs: unknown[] = [];
  constructor(public stream: MediaStream, public opts: MediaRecorderOptions) {
    FakeRecorder.last = this;
  }
  start(...a: unknown[]) {
    this.startArgs = a;
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["b"]) });
    this.onstop?.();
  }
}

const trackStop = vi.fn();
const ctxClose = vi.fn(async () => {});
let rafCb: (() => void) | null;

beforeEach(() => {
  rafCb = null;
  trackStop.mockClear();
  ctxClose.mockClear();
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  vi.stubGlobal("requestAnimationFrame", (cb: () => void) => {
    rafCb = cb;
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  vi.stubGlobal(
    "AudioContext",
    class {
      createMediaStreamSource() {
        return { connect() {} };
      }
      createAnalyser() {
        return { fftSize: 0, getFloatTimeDomainData: (a: Float32Array) => a.fill(0.01) };
      }
      close = ctxClose;
    },
  );
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop: trackStop }, { stop: trackStop }] })) },
  });
});
afterEach(() => vi.unstubAllGlobals());

describe("startRecorder", () => {
  it("asks for audio and starts with the mime, 64 kbit/s and a 250 ms slice", async () => {
    await startRecorder({ mime: "audio/webm;codecs=opus" });
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(FakeRecorder.last.opts).toEqual({ mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 64000 });
    expect(FakeRecorder.last.startArgs).toEqual([250]);
  });

  it("writes analyser levels to the module ref", async () => {
    const onLevel = vi.fn();
    await startRecorder({ mime: "audio/mp4", onLevel });
    rafCb?.();
    expect(recorderLevel()).toBeCloseTo(0.4, 5);
    expect(onLevel).toHaveBeenCalledWith(expect.closeTo(0.4, 5));
  });

  it("stop resolves one blob with the mime and releases everything", async () => {
    const rec = await startRecorder({ mime: "audio/webm;codecs=opus" });
    const blob = await rec.stop();
    expect(blob.type).toBe("audio/webm;codecs=opus");
    expect(blob.size).toBe(1);
    expect(trackStop).toHaveBeenCalledTimes(2);
    expect(ctxClose).toHaveBeenCalled();
    expect(recorderLevel()).toBe(0);
  });
});
