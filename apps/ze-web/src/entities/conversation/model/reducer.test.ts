import type { MessageSchema as Message, WsInboundFrame, WsScreenContext } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { emptyThread, reduce, type ConversationEvent, type ConversationState } from "./reducer";

const T = "t1";
const msg = (over: Partial<Message> = {}): Message => ({
  id: "m1",
  role: "assistant",
  text: "hi",
  components: [],
  read: false,
  thread_id: T,
  created_at: "2026-10-18T10:00:00Z",
  ...over,
});
const ctx = { activeThreadId: T };
const run = (events: ConversationEvent[], start: ConversationState = { byThread: {} }, now = 1000) =>
  events.reduce((s, e, i) => reduce(s, e, now + i * 10, ctx), start);
const th = (s: ConversationState, id = T) => s.byThread[id] ?? emptyThread();
const frame = <K extends WsInboundFrame["type"]>(f: Extract<WsInboundFrame, { type: K }>) => f as ConversationEvent;
const sent = (over = {}): ConversationEvent => ({
  type: "sent",
  threadId: T,
  text: "hello",
  context: {} as WsScreenContext,
  ...over,
});

describe("turn phases", () => {
  it("walks awaiting → thinking → speaking → idle and accumulates streaming text", () => {
    let s = run([sent()]);
    expect(th(s).turn.phase).toBe("awaiting");
    s = run([frame({ type: "typing", thread_id: T, text: "routing" })], s);
    expect(th(s).turn.phase).toBe("thinking");
    expect(th(s).turn.typingText).toBe("routing");
    s = run([frame({ type: "token", thread_id: T, text: "He" }), frame({ type: "token", thread_id: T, text: "llo" })], s);
    expect(th(s).turn.phase).toBe("speaking");
    expect(th(s).turn.streamingText).toBe("Hello");
    s = run([frame({ type: "message", message: msg() })], s);
    expect(th(s).turn).toMatchObject({ phase: "idle", streamingText: "", typingText: null });
    expect(th(s).messages.map((m) => m.id)).toContain("m1");
  });

  it("updates only the thread a frame names", () => {
    const s = run([sent(), frame({ type: "typing", thread_id: "other", text: "x" })]);
    expect(th(s).turn.phase).toBe("awaiting");
    expect(th(s, "other").turn.phase).toBe("thinking");
  });

  it("applies an untagged error only to a running thread", () => {
    const idle = run([frame({ type: "error", detail: "boom" })]);
    expect(th(idle).turn.phase).toBe("idle");
    const running = run([sent(), frame({ type: "error", detail: "boom" })]);
    expect(th(running).turn.phase).toBe("failed");
  });

  it("keeps the phase and sets a busy outcome on error code busy", () => {
    const s = run([sent(), frame({ type: "error", thread_id: T, detail: "Ze is busy", code: "busy" })]);
    expect(th(s).turn.phase).toBe("awaiting");
    expect(th(s).lastOutcome).toMatchObject({ kind: "busy", detail: "Ze is busy" });
  });

  it("maps retry error codes to outcomes and ends the wait", () => {
    const plan = [{ entry_id: "e", tool: "x", effect_phrase: "did x" }];
    const s = run([
      { type: "retry_sent", threadId: T, messageId: "m1" },
      frame({ type: "error", thread_id: T, detail: "partial", code: "retry_partial", plan }),
    ]);
    expect(th(s).turn.phase).toBe("idle");
    expect(th(s).lastOutcome).toMatchObject({ kind: "retry_partial", plan });
    const failed = run([
      { type: "retry_sent", threadId: T, messageId: "m1" },
      frame({ type: "error", thread_id: T, detail: "x", code: "retry_failed", rolled_back: true }),
    ]);
    expect(th(failed).lastOutcome?.kind).toBe("rolled_back_retry_failed");
  });
});

describe("messages", () => {
  it("patches text and components on edit", () => {
    const s = run([
      frame({ type: "message", message: msg() }),
      frame({ type: "edit", id: "m1", thread_id: T, text: "new", components: [{ type: "text" }] }),
    ]);
    expect(th(s).messages[0]).toMatchObject({ text: "new", components: [{ type: "text" }] });
  });

  it("marks a superseded message and sets rollback", () => {
    const s = run([
      frame({ type: "message", message: msg() }),
      frame({ type: "message", message: msg({ id: "m2", created_at: "2026-10-18T10:01:00Z" }) }),
      frame({ type: "message_superseded", thread_id: T, message_id: "m1", replaced_by: "m2" }),
      frame({
        type: "message_rollback",
        thread_id: T,
        message_id: "m2",
        rollback: { state: "partial", entries: [] } as never,
      }),
    ]);
    expect(th(s).messages.find((m) => m.id === "m1")?.replaced_by).toBe("m2");
    expect(th(s).messages.find((m) => m.id === "m2")?.rollback).toMatchObject({ state: "partial" });
  });

  it("ends a retry wait when the rollback state is rolled_back_retry_failed", () => {
    const s = run([
      frame({ type: "message", message: msg() }),
      { type: "retry_sent", threadId: T, messageId: "m1" },
      frame({
        type: "message_rollback",
        thread_id: T,
        message_id: "m1",
        rollback: { state: "rolled_back_retry_failed", entries: [] } as never,
      }),
    ]);
    expect(th(s).turn.phase).toBe("idle");
  });

  it("adds an optimistic user line on sent and keeps the original on resend", () => {
    let s = run([sent()]);
    expect(th(s).messages).toHaveLength(1);
    expect(th(s).messages[0]).toMatchObject({ role: "user", text: "hello" });
    const at = th(s).turn.lastSent!.at;
    s = run([{ type: "delivery_failed", threadId: T }], s);
    expect(th(s).turn.phase).toBe("failed");
    s = run([sent({ resend: true })], s, 9000);
    expect(th(s).messages).toHaveLength(1);
    expect(th(s).turn.phase).toBe("awaiting");
    expect(th(s).turn.lastSent!.at).toBe(at);
  });

  it("merges history by id in created_at order and drops the optimistic duplicate", () => {
    const s = run([
      sent(),
      { type: "history_loaded", threadId: T, messages: [
        msg({ id: "b", created_at: "2026-10-18T10:02:00Z" }),
        msg({ id: "u", role: "user", text: "hello", read: true, created_at: "2026-10-18T10:01:00Z" }),
        msg({ id: "a", created_at: "2026-10-18T10:00:00Z" }),
      ] },
    ]);
    expect(th(s).historyLoaded).toBe(true);
    expect(th(s).messages.map((m) => m.id)).toEqual(["a", "u", "b"]);
  });
});

describe("pause, attention, bookkeeping", () => {
  it("pauses only a running thread and resumes with a fresh clock", () => {
    const idle = run([{ type: "paused", threadId: T }]);
    expect(th(idle).turn.phase).toBe("idle");
    let s = run([sent(), { type: "paused", threadId: T }]);
    expect(th(s).turn.phase).toBe("paused");
    s = run([{ type: "resumed", threadId: T }], s, 5000);
    expect(th(s).turn.phase).toBe("awaiting");
    expect(th(s).turn.activityAt).toBe(5000);
  });

  it("resumes an idle thread (a confirmation replayed after reload) and ends a wait when history holds a new reply", () => {
    let s = run([{ type: "resumed", threadId: T }]);
    expect(th(s).turn.phase).toBe("awaiting");
    s = run([{ type: "history_loaded", threadId: T, messages: [msg({ id: "new" })] }], s);
    expect(th(s).turn.phase).toBe("idle");
  });

  it("sets attention for an assistant message on another thread and opened clears it", () => {
    let s = run([frame({ type: "message", message: msg({ thread_id: "other" }) })]);
    expect(th(s, "other").attention).toBe(true);
    s = run([{ type: "opened", threadId: "other" }], s);
    expect(th(s, "other").attention).toBe(false);
    s = run([frame({ type: "message", message: msg({ id: "z" }) })]);
    expect(th(s).attention).toBe(false);
  });

  it("records lastMessageAt and lastError on an idle thread", () => {
    const s = run([
      frame({ type: "message", message: msg() }),
      frame({ type: "error", thread_id: T, detail: "nope", code: null }),
    ]);
    expect(th(s).lastMessageAt).toBe(1000);
    expect(th(s).lastError).toMatchObject({ detail: "nope", at: 1010 });
  });
});

describe("ui_version", () => {
  it("keeps the version a live message frame carried", () => {
    const s = run([frame({ type: "message", message: msg(), ui_version: "2.0" })]);
    expect(th(s).messages[0]).toMatchObject({ id: "m1", ui_version: "2.0" });
  });

  it("history does not strip the version of a reply seen live", () => {
    let s = run([frame({ type: "message", message: msg(), ui_version: "2.0" })]);
    s = run([{ type: "history_loaded", threadId: T, messages: [msg()] }], s);
    expect(th(s).messages[0]).toMatchObject({ ui_version: "2.0" });
  });

  it("a message without a frame version has none", () => {
    const s = run([frame({ type: "message", message: msg() })]);
    expect(th(s).messages[0].ui_version).toBeUndefined();
  });
});
