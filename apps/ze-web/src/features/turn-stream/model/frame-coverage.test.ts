import type { WsInboundFrame } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { FRAME_REGISTRY, type FrameType } from "./frame-registry";

// A new frame type on the wire fails to compile here until it is listed.
const ALL_FRAMES: Record<WsInboundFrame["type"], true> = {
  message: true,
  edit: true,
  confirm_request: true,
  confirm_cancel: true,
  typing: true,
  token: true,
  error: true,
  message_superseded: true,
  message_rollback: true,
  refresh: true,
  pong: true,
  trace_update: true,
  notification: true,
};

const sources = import.meta.glob(["/src/**/*.ts", "/src/**/*.tsx", "!/src/**/*.test.ts", "!/src/**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const CALL = /useFrame\(\s*"([a-z_]+)"/g;
const found = Object.entries(sources).flatMap(([path, text]) =>
  [...text.matchAll(CALL)].map((m) => ({ file: path.replace("/src/", ""), frame: m[1] as FrameType })),
);

describe("frame coverage (SC-001)", () => {
  it("gives every inbound frame exactly one state owner, or an explicit none", () => {
    for (const frame of Object.keys(ALL_FRAMES) as FrameType[]) {
      const owners = FRAME_REGISTRY.filter((e) => e.frame === frame && e.role !== "listener");
      expect(owners, frame).toHaveLength(1);
    }
  });

  it("registers every useFrame call site", () => {
    const registered = new Set(FRAME_REGISTRY.filter((e) => e.file).map((e) => `${e.file}::${e.frame}`));
    const missing = found.filter((f) => !registered.has(`${f.file}::${f.frame}`)).map((f) => `${f.file}::${f.frame}`);
    expect(missing).toEqual([]);
  });

  it("lists no entry whose call site is gone", () => {
    const real = new Set(found.map((f) => `${f.file}::${f.frame}`));
    const stale = FRAME_REGISTRY.filter((e) => e.file && !real.has(`${e.file}::${e.frame}`)).map((e) => `${e.file}::${e.frame}`);
    expect(stale).toEqual([]);
  });

  it("gives every entry a reason", () => {
    expect(FRAME_REGISTRY.filter((e) => !e.reason.trim())).toEqual([]);
  });

  it("keeps listeners away from the conversation store", () => {
    const listenerFiles = new Set(FRAME_REGISTRY.filter((e) => e.role === "listener" && e.file !== "features/turn-stream/ui/TurnFrameHandler.tsx").map((e) => e.file!));
    const offenders = [...listenerFiles].filter((f) => /useConversation|entities\/conversation/.test(sources[`/src/${f}`] ?? ""));
    expect(offenders).toEqual([]);
  });
});
