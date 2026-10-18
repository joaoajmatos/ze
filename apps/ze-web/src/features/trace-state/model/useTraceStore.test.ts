import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { tracesForThread, useTraceStore } from "./useTraceStore";

function frame(
  threadId: string,
  messageId: string,
  extra: Partial<WsTraceUpdateFrame> = {},
): WsTraceUpdateFrame {
  return {
    type: "trace_update",
    thread_id: threadId,
    message_id: messageId,
    agent: extra.agent ?? "companion",
    routing_method: "embedding",
    confidence: 0.9,
    score_gap: 0.1,
    is_compound: false,
    subtasks: [],
    memory_chunks: [],
    tool_calls: [],
    total_duration_ms: 10,
    skills_used: [],
    conductor_hint: extra.conductor_hint ?? null,
    conductor_ledger: extra.conductor_ledger ?? [],
    ...extra,
  };
}

function tracesVisibleFor(threadId: string): string[] {
  const state = useTraceStore.getState();
  return tracesForThread(state, threadId).map((t) => t.message_id);
}

describe("per-thread trace isolation", () => {
  beforeEach(() => {
    useTraceStore.setState({
      byThread: {},
    });
  });

  it("does not make thread B trace_update the visible trace while A is active", () => {
    useTraceStore.getState().commitPendingTrace(
      frame("thread-a", "msg-a", {
        agent: "conductor-a",
        conductor_ledger: [{ agent: "research", status: "running" }],
      }),
    );
    useTraceStore.getState().commitPendingTrace(
      frame("thread-b", "msg-b", {
        agent: "calendar",
        conductor_ledger: [{ agent: "calendar", status: "done" }],
      }),
    );

    expect(tracesVisibleFor("thread-a")).toEqual(["msg-a"]);
    expect(tracesVisibleFor("thread-a")).not.toContain("msg-b");
    expect(tracesVisibleFor("thread-b")).toEqual(["msg-b"]);
  });

  it("drops trace_update frames with no thread_id instead of applying them globally", () => {
    useTraceStore.getState().commitPendingTrace(frame("thread-a", "msg-a"));
    const orphan = frame("thread-a", "orphan");
    delete (orphan as { thread_id?: string }).thread_id;
    useTraceStore.getState().commitPendingTrace(orphan);

    expect(tracesVisibleFor("thread-a")).toEqual(["msg-a"]);
    expect(tracesVisibleFor("thread-a")).not.toContain("orphan");
  });

  it("does not merge a partial B update into A's pending live trace", () => {
    useTraceStore.getState().mergePartialTrace({
      thread_id: "thread-a",
      agent: "companion",
      conductor_ledger: [{ agent: "research", status: "running" }],
    });
    useTraceStore.getState().mergePartialTrace({
      thread_id: "thread-b",
      agent: "calendar",
      conductor_ledger: [{ agent: "calendar", status: "done" }],
    });

    const pendingA = useTraceStore.getState().byThread["thread-a"]?.pendingTrace;
    expect(pendingA?.agent).toBe("companion");
    expect(pendingA?.conductor_ledger?.[0]?.agent).toBe("research");
  });
});

describe("arrival stamps (trace instruments)", () => {
  beforeEach(() => {
    useTraceStore.setState({ byThread: {} });
    vi.useFakeTimers();
    vi.setSystemTime(10_000);
  });
  afterEach(() => vi.useRealTimers());

  const partial = (extra: Partial<WsTraceUpdateFrame>) => useTraceStore.getState().mergePartialTrace({ thread_id: "t", ...extra });
  const bucket = () => useTraceStore.getState().byThread.t;

  it("stamps each stage once, by the fields the partial carries", () => {
    partial({ agent: "companion", routing_method: "embedding" });
    vi.setSystemTime(10_400);
    partial({ screen: { route: "/doing" } as never });
    vi.setSystemTime(10_900);
    partial({ memory_chunks: [{ text: "a", score: 0.9, source: "fact", extraction_confidence: null }] });
    vi.setSystemTime(11_000);
    partial({ memory_chunks: [{ text: "b", score: 0.8, source: "fact", extraction_confidence: null }] });
    partial({ tier: { agent: "companion", tier: "full", decided_by: "default", model: "m" } as never });
    partial({ tool_calls: [{ name: "x", call_index: 0 } as never] });
    expect(bucket().pendingArrivals).toEqual({ route: 10_000, screen: 10_400, memory: 10_900, tier: 11_000, "tool:0": 11_000 });
  });

  it("moves the stamps to arrivalsByMessage on commit and clears the pending ones", () => {
    partial({ agent: "companion" });
    useTraceStore.getState().commitPendingTrace(frame("t", "m1"));
    expect(bucket().arrivalsByMessage.m1).toEqual({ route: 10_000 });
    expect(bucket().pendingArrivals).toEqual({});
  });

  it("gives a hydrated trace no arrivals and starts a second turn fresh", () => {
    useTraceStore.getState().mergeTraces("t", [frame("t", "old")], ["old"]);
    expect(bucket().arrivalsByMessage.old).toBeUndefined();
    partial({ agent: "companion" });
    useTraceStore.getState().commitPendingTrace(frame("t", "m1"));
    vi.setSystemTime(20_000);
    partial({ agent: "research" });
    useTraceStore.getState().commitPendingTrace(frame("t", "m2"));
    expect(bucket().arrivalsByMessage.m2).toEqual({ route: 20_000 });
    expect(bucket().arrivalsByMessage.m1).toEqual({ route: 10_000 });
  });

  it("resetPending drops a stale pending trace so a refused turn never lends its stamps", () => {
    partial({ agent: "companion" });
    useTraceStore.getState().resetPending("t");
    expect(bucket().pendingTrace).toBeNull();
    expect(bucket().pendingArrivals).toEqual({});
  });
});
