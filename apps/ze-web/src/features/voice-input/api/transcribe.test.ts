import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ transcribeVoice: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ transcribeVoice: m.transcribeVoice }));
import { transcribe, VoiceError } from "./transcribe";

const blob = new Blob(["x"]);
const result = (status: number, error: unknown) => ({ data: undefined, error, response: { status } });

async function fails(status: number, error: unknown): Promise<VoiceError> {
  m.transcribeVoice.mockResolvedValueOnce(result(status, error));
  return transcribe(blob, "audio/webm;codecs=opus").then(
    () => {
      throw new Error("expected a failure");
    },
    (e) => e as VoiceError,
  );
}

beforeEach(() => m.transcribeVoice.mockReset());

describe("transcribe", () => {
  it("sends a File named recording.<ext> with the mime as its type", async () => {
    m.transcribeVoice.mockResolvedValueOnce({ data: { transcript: "hi", duration_s: 1, transcription_id: "t1" }, response: { status: 200 } });
    await expect(transcribe(blob, "audio/mp4")).resolves.toEqual({ transcript: "hi", transcriptionId: "t1" });
    const file = m.transcribeVoice.mock.calls[0][0].body.file as File;
    expect(file.name).toBe("recording.m4a");
    expect(file.type).toBe("audio/mp4");
  });

  it.each([422, 502, 500])("%i is retryable with the server's line", async (status) => {
    const e = await fails(status, { detail: "Server line." });
    expect([e.kind, e.detail]).toEqual(["retryable", "Server line."]);
  });

  it("falls back to the plain line when there is no detail", async () => {
    const e = await fails(502, "<html>bad gateway</html>");
    expect([e.kind, e.detail]).toEqual(["retryable", "I couldn't make out the recording."]);
  });

  it("a network failure is retryable", async () => {
    m.transcribeVoice.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(transcribe(blob, "audio/mp4")).rejects.toMatchObject({ kind: "retryable", detail: "I couldn't make out the recording." });
  });

  it("413 and 415 need a new recording", async () => {
    const big = await fails(413, { detail: "That recording is too long: the limit is 2 minutes." });
    expect([big.kind, big.detail]).toEqual(["rerecord", "That recording is too long: the limit is 2 minutes."]);
    expect((await fails(413, "too big")).detail).toBe("The recording is too large. Record a shorter one.");
    const fmt = await fails(415, "nope");
    expect([fmt.kind, fmt.detail]).toEqual(["rerecord", "This recording format isn't supported."]);
  });

  it("503 is unavailable", async () => {
    const e = await fails(503, "gateway");
    expect([e.kind, e.detail]).toEqual(["unavailable", "Voice input is not available on this server."]);
    expect((await fails(503, { detail: "Off here." })).detail).toBe("Off here.");
  });
});
