import { beforeEach, describe, expect, it } from "vitest";
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
      traces: [],
      pending: false,
      pendingTrace: null,
      hydrating: false,
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
