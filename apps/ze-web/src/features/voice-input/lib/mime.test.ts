import { describe, expect, it } from "vitest";
import { extensionFor, pickMime } from "./mime";

const only = (...ok: string[]) => (m: string) => ok.includes(m);

describe("pickMime", () => {
  it("prefers WebM opus", () => {
    expect(pickMime(() => true)).toBe("audio/webm;codecs=opus");
  });
  it("falls back to Ogg opus", () => {
    expect(pickMime(only("audio/ogg;codecs=opus", "audio/mp4"))).toBe("audio/ogg;codecs=opus");
  });
  it("falls back to MP4", () => {
    expect(pickMime(only("audio/mp4"))).toBe("audio/mp4");
  });
  it("returns null with none", () => {
    expect(pickMime(() => false)).toBeNull();
  });
});

describe("extensionFor", () => {
  it("maps each mime", () => {
    expect(extensionFor("audio/webm;codecs=opus")).toBe("webm");
    expect(extensionFor("audio/ogg;codecs=opus")).toBe("ogg");
    expect(extensionFor("audio/mp4")).toBe("m4a");
  });
});
