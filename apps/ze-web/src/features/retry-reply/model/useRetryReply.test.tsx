import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { send, handlers } = vi.hoisted(() => ({
  send: vi.fn(),
  handlers: new Map<string, (f: unknown) => void>(),
}));

vi.mock("@/shared/api", async () => {
  const { create } = await import("zustand");
  const useWsStore = create<{
    thinkingThreads: Record<string, boolean>;
    setThreadThinking: (t: string, v: boolean) => void;
  }>((set) => ({
    thinkingThreads: {},
    setThreadThinking: (t, v) => set((s) => ({ thinkingThreads: { ...s.thinkingThreads, [t]: v } })),
  }));
  return {
    send,
    useWsStore,
    useFrame: (type: string, h: (f: unknown) => void) => handlers.set(type, h),
  };
});

import { useWsStore } from "@/shared/api";
import { useRetryReply } from "./useRetryReply";

function setup() {
  const onSuperseded = vi.fn();
  const onNotice = vi.fn();
  const queryClient = new QueryClient();
  const spy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const hook = renderHook(() => useRetryReply({ threadId: "t1", onSuperseded, onNotice }), {
    wrapper,
  });
  return { ...hook, onSuperseded, onNotice, spy };
}

describe("useRetryReply", () => {
  beforeEach(() => {
    send.mockReset();
    handlers.clear();
    (useWsStore as unknown as { setState: (s: object) => void }).setState({ thinkingThreads: {} });
  });

  it("sends the retry frame and tracks retrying", () => {
    send.mockReturnValue(true);
    const { result } = setup();
    act(() => void result.current.retry("m1"));
    expect(send).toHaveBeenCalledWith({ type: "retry", message_id: "m1", thread_id: "t1" });
    expect(result.current.retrying).toBe(true);
    expect(result.current.retryingId).toBe("m1");
  });

  it("refuses a second retry while one is running", () => {
    send.mockReturnValue(true);
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

  it("swaps the reply and refreshes feedback and traces on message_superseded", () => {
    send.mockReturnValue(true);
    const { result, onSuperseded, spy } = setup();
    act(() => void result.current.retry("m1"));
    act(() =>
      handlers.get("message_superseded")!({
        type: "message_superseded",
        message_id: "m1",
        replaced_by: "m2",
        thread_id: "t1",
      }),
    );
    expect(onSuperseded).toHaveBeenCalledWith("m1", "m2");
    expect(spy).toHaveBeenCalled();
  });

  it("keeps the original and shows a notice on retry_failed", () => {
    send.mockReturnValue(true);
    const { result, onNotice, onSuperseded } = setup();
    act(() => void result.current.retry("m1"));
    act(() =>
      handlers.get("error")!({ type: "error", thread_id: "t1", detail: "x", code: "retry_failed" }),
    );
    expect(onNotice).toHaveBeenCalledWith(expect.stringMatching(/retry failed/i));
    expect(onSuperseded).not.toHaveBeenCalled();
  });

  it("shows the server reason on retry_unavailable", () => {
    send.mockReturnValue(true);
    const { result, onNotice } = setup();
    act(() => void result.current.retry("m1"));
    act(() =>
      handlers.get("error")!({
        type: "error",
        thread_id: "t1",
        detail: "x",
        code: "retry_unavailable",
        reason_code: "has_write_action",
        reason_text: "This reply set a reminder.",
      }),
    );
    expect(onNotice).toHaveBeenCalledWith("This reply set a reminder.");
  });

  it("surfaces busy without swapping anything", () => {
    send.mockReturnValue(true);
    const { result, onNotice } = setup();
    act(() => void result.current.retry("m1"));
    act(() =>
      handlers.get("error")!({ type: "error", thread_id: "t1", detail: "Ze is busy", code: "busy" }),
    );
    expect(onNotice).toHaveBeenCalledWith("Ze is busy");
  });
});
