import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { send } = vi.hoisted(() => ({ send: vi.fn((_f: unknown) => true) }));
vi.mock("@/shared/api", () => ({ send }));
vi.mock("@/entities/session", () => ({ useSession: { getState: () => ({ threadId: "t1" }) } }));

import { useConversation } from "@/entities/conversation";
import { useRetryReply } from "./useRetryReply";

const apply = (e: Parameters<ReturnType<typeof useConversation.getState>["apply"]>[0]) =>
  act(() => useConversation.getState().apply(e, { activeThreadId: "t1" }));

function setup() {
  const onNotice = vi.fn();
  const queryClient = new QueryClient();
  const spy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  const hook = renderHook(() => useRetryReply({ threadId: "t1", onNotice }), { wrapper });
  return { ...hook, onNotice, spy };
}

beforeEach(() => {
  send.mockReset();
  send.mockReturnValue(true);
  useConversation.setState({ byThread: {} });
});

describe("useRetryReply", () => {
  it("sends the retry frame and tracks retrying", () => {
    const { result } = setup();
    act(() => void result.current.retry("m1"));
    expect(send).toHaveBeenCalledWith({ type: "retry", message_id: "m1", thread_id: "t1" });
    expect(result.current.retrying).toBe(true);
    expect(result.current.retryingId).toBe("m1");
  });

  it("refuses a second retry while one is running", () => {
    const { result } = setup();
    act(() => void result.current.retry("m1"));
    act(() => void result.current.retry("m1"));
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("notifies when the socket is down", () => {
    send.mockReturnValue(false);
    const { result, onNotice } = setup();
    act(() => void result.current.retry("m1"));
    expect(onNotice).toHaveBeenCalled();
    expect(result.current.retrying).toBe(false);
  });

  it("sends confirmed_plan when given", () => {
    const { result } = setup();
    act(() => void result.current.retry("m1", ["e1", "e2"]));
    expect(send).toHaveBeenCalledWith({ type: "retry", message_id: "m1", thread_id: "t1", confirmed_plan: ["e1", "e2"] });
  });

  it("refreshes feedback and traces when a reply is superseded or a rollback lands, and stops retrying", () => {
    const { result, spy } = setup();
    apply({ type: "message", message: { id: "m1", role: "assistant", text: "a", components: [], read: true, thread_id: "t1", created_at: "2026-10-18T10:00:00Z" } });
    act(() => void result.current.retry("m1", ["e1"]));
    spy.mockClear();
    apply({ type: "message_rollback", thread_id: "t1", message_id: "m1", rollback: { state: "partial", entries: [] } as never });
    expect(spy).toHaveBeenCalled();
    expect(result.current.retrying).toBe(true);
    spy.mockClear();
    apply({ type: "message", message: { id: "m2", role: "assistant", text: "b", components: [], read: true, thread_id: "t1", created_at: "2026-10-18T10:01:00Z" } });
    apply({ type: "message_superseded", thread_id: "t1", message_id: "m1", replaced_by: "m2" });
    expect(spy).toHaveBeenCalled();
    expect(result.current.retrying).toBe(false);
  });

  it("exposes the server's outcome for the notice and ends the retry", () => {
    const { result } = setup();
    act(() => void result.current.retry("m1", ["e1"]));
    apply({ type: "error", thread_id: "t1", detail: "x", code: "retry_unavailable", reason_text: "This reply set a reminder." });
    expect(result.current.outcome).toMatchObject({ kind: "error", detail: "This reply set a reminder." });
    expect(result.current.retrying).toBe(false);
  });

  it("says what was undone on retry_failed with rolled_back", () => {
    const { result } = setup();
    act(() => void result.current.retry("m1", ["e1"]));
    apply({ type: "error", thread_id: "t1", detail: "Ze undid set a reminder but could not write a new reply.", code: "retry_failed", rolled_back: true });
    expect(result.current.outcome).toMatchObject({ kind: "rolled_back_retry_failed", detail: "Ze undid set a reminder but could not write a new reply." });
  });

  it("stops retrying when a paused retry ends as rolled_back_retry_failed with no error frame", () => {
    const { result } = setup();
    act(() => void result.current.retry("m1", ["e1"]));
    apply({ type: "message_rollback", thread_id: "t1", message_id: "m1", rollback: { state: "rolled_back_retry_failed", entries: [] } as never });
    expect(result.current.retrying).toBe(false);
    expect(result.current.retryingId).toBeNull();
  });
});
