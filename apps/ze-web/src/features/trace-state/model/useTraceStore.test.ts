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
    tool_duration_ms: 10,
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

describe("partial telemetry frames", () => {
  beforeEach(() => useTraceStore.setState({ byThread: {} }));

  const partial = (extra: Partial<WsTraceUpdateFrame>) => useTraceStore.getState().mergePartialTrace({ thread_id: "t", message_id: "m1", ...extra });
  const bucket = () => useTraceStore.getState().byThread.t;
  const stage = (name: string, start_ms: number, run = 1) => ({ name, start_ms, duration_ms: 10, run });

  it("appends stages in arrival order", () => {
    partial({ stages: [stage("fetch_context", 200)] });
    partial({ stages: [stage("embed_route", 50)] });
    expect(bucket().pendingTrace?.stages?.map((x) => x.name)).toEqual(["fetch_context", "embed_route"]);
  });

  it("keeps a stage repeated with the same run, name and start once", () => {
    partial({ stages: [stage("embed_route", 50)] });
    partial({ stages: [stage("embed_route", 50)] });
    partial({ stages: [stage("embed_route", 50, 2)] });
    partial({ stages: [stage("embed_route", 90)] });
    expect(bucket().pendingTrace?.stages).toHaveLength(3);
  });

  it("merges tool rows by call_id: a second row with the same id replaces the first in place", () => {
    const call = (call_id: string, gate: string, name = "send_email") => ({ call_id, name, gate, duration_ms: 0, success: true, result_snippet: "" });
    partial({ tool_calls: [call("a", "none", "list_events"), call("b", "parked")] as never });
    partial({ tool_calls: [{ ...call("b", "approved"), duration_ms: 300 }] as never });
    expect(bucket().pendingTrace?.tool_calls?.map((c) => [c.call_id, c.gate])).toEqual([["a", "none"], ["b", "approved"]]);
    expect(bucket().pendingTrace?.tool_calls?.[1].duration_ms).toBe(300);
  });

  it("ignores a partial that arrives after the message's committed trace", () => {
    useTraceStore.getState().commitPendingTrace(frame("t", "m1", { agent: "companion" }));
    partial({ stages: [stage("fetch_context", 200)], agent: "late" });
    expect(bucket().pendingTrace).toBeNull();
    expect(bucket().traces[0].agent).toBe("companion");
  });

  it("replaces the pending trace with the committed one and its server stages", () => {
    partial({ stages: [stage("fetch_context", 200)] });
    useTraceStore.getState().commitPendingTrace(frame("t", "m1", { stages: [stage("fetch_context", 200), stage("synthesize", 900)] }));
    expect(bucket().pendingTrace).toBeNull();
    expect(bucket().traces[0].stages?.map((x) => x.name)).toEqual(["fetch_context", "synthesize"]);
  });

  it("holds no client arrival stamps", () => {
    partial({ agent: "companion" });
    useTraceStore.getState().commitPendingTrace(frame("t", "m1"));
    useTraceStore.getState().resetPending("t");
    const keys = Object.keys(bucket());
    for (const gone of ["pendingArrivals", "arrivalsByMessage", "pendingSentAt", "sentAtByMessage"]) expect(keys).not.toContain(gone);
  });

  it("resetPending drops a stale pending trace", () => {
    partial({ agent: "companion" });
    useTraceStore.getState().resetPending("t");
    expect(bucket().pendingTrace).toBeNull();
  });
});
