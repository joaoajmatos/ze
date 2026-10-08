import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DELIVERY_WATCHDOG_MS, useChatWorkspace } from "./useChatWorkspace";

type Handler = (frame: Record<string, unknown>) => void;
const handlers = new Map<string, Handler>();
const sendMock = vi.fn((_frame: unknown) => true);
const listMessagesMock = vi.fn();

vi.mock("@myguyze/ze-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@myguyze/ze-client")>()),
  listMessages: (...args: unknown[]) => listMessagesMock(...args),
}));

vi.mock("@/shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api")>()),
  send: (frame: unknown) => sendMock(frame),
  useFrame: (type: string, handler: Handler) => {
    handlers.set(type, handler);
  },
}));

vi.mock("@/features/respond-to-confirmation", () => ({
  useConfirmation: () => ({ pendingConfirm: null, respond: vi.fn(), clear: vi.fn() }),
}));

import { useWsStore } from "@/shared/api";

const THREAD = "thread-1";

function message(id: string, role: "user" | "assistant", text: string, thread = THREAD) {
  return {
    id,
    role,
    text,
    components: [],
    read: true,
    created_at: new Date().toISOString(),
    thread_id: thread,
  };
}

function setup(options: Parameters<typeof useChatWorkspace>[0] = {}) {
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);
  return renderHook(() => useChatWorkspace({ threadId: THREAD, ...options }), { wrapper });
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("useChatWorkspace delivery watchdog", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    handlers.clear();
    sendMock.mockClear();
    sendMock.mockReturnValue(true);
    listMessagesMock.mockReset();
    listMessagesMock.mockResolvedValue({ data: [] });
    useWsStore.setState({
      isConnected: true,
      thinkingThreads: {},
      typingTextThreads: {},
      attentionThreads: {},
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function sendHello(hook: ReturnType<typeof setup>) {
    await flush();
    act(() => {
      hook.result.current.sendMessage("hello");
    });
    listMessagesMock.mockClear();
  }

  it("re-fetches history when no reply arrives within the bound", async () => {
    const hook = setup();
    await sendHello(hook);
    expect(hook.result.current.isThinking).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS - 1);
    });
    expect(listMessagesMock).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(listMessagesMock).toHaveBeenCalledTimes(1);
    expect(listMessagesMock).toHaveBeenCalledWith({ query: { thread_id: THREAD, limit: 200 } });
  });

  it("shows the stored reply and unlocks when history has it", async () => {
    const hook = setup();
    await sendHello(hook);
    listMessagesMock.mockResolvedValue({
      data: [message("u1", "user", "hello"), message("a1", "assistant", "hi there")],
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS);
    });

    expect(hook.result.current.isThinking).toBe(false);
    expect(hook.result.current.deliveryFailed).toBe(false);
    expect(hook.result.current.messages.map((m) => m.text)).toEqual(["hello", "hi there"]);
  });

  it("exposes deliveryFailed and unlocks when history has no reply", async () => {
    const hook = setup();
    await sendHello(hook);
    listMessagesMock.mockResolvedValue({ data: [message("u1", "user", "hello")] });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS);
    });

    expect(hook.result.current.isThinking).toBe(false);
    expect(hook.result.current.deliveryFailed).toBe(true);
  });

  it("does not time out while typing frames keep arriving", async () => {
    const hook = setup();
    await sendHello(hook);

    for (let i = 0; i < 4; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS / 2);
      });
      act(() => handlers.get("typing")?.({ type: "typing", thread_id: THREAD, text: "Working…" }));
    }

    expect(listMessagesMock).not.toHaveBeenCalled();
    expect(hook.result.current.isThinking).toBe(true);
  });

  it("cancels the wait when the reply frame arrives", async () => {
    const hook = setup();
    await sendHello(hook);

    act(() =>
      handlers.get("message")?.({
        type: "message",
        message: message("a1", "assistant", "hi there"),
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS * 2);
    });

    expect(hook.result.current.isThinking).toBe(false);
    expect(hook.result.current.deliveryFailed).toBe(false);
    expect(listMessagesMock).not.toHaveBeenCalled();
  });

  it("retry() re-sends the last message without duplicating its bubble", async () => {
    const hook = setup();
    await sendHello(hook);
    listMessagesMock.mockResolvedValue({ data: [message("u1", "user", "hello")] });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS);
    });
    expect(hook.result.current.deliveryFailed).toBe(true);
    sendMock.mockClear();

    act(() => {
      hook.result.current.retry();
    });

    expect(sendMock).toHaveBeenCalledWith(
      expect.objectContaining({ type: "message", text: "hello", thread_id: THREAD }),
    );
    expect(hook.result.current.deliveryFailed).toBe(false);
    expect(hook.result.current.isThinking).toBe(true);
    expect(hook.result.current.messages.filter((m) => m.role === "user")).toHaveLength(1);
  });

  it("shows the retry state when the server reports an error for this turn", async () => {
    const hook = setup();
    await sendHello(hook);

    act(() => handlers.get("error")?.({ type: "error", detail: "boom", thread_id: THREAD }));

    expect(hook.result.current.isThinking).toBe(false);
    expect(hook.result.current.deliveryFailed).toBe(true);
  });

  it("ignores an untagged error when this hook has no send in flight", async () => {
    const hook = setup();
    await flush();
    act(() => useWsStore.getState().setThreadThinking(THREAD, true));

    act(() => handlers.get("error")?.({ type: "error", detail: "thread_id required" }));

    expect(hook.result.current.isThinking).toBe(true);
  });

  it("sends thread_id from the ephemeral path", async () => {
    const hook = setup({ ephemeral: true });
    await flush();

    act(() => {
      hook.result.current.sendMessage("hello");
    });

    expect(sendMock).toHaveBeenCalledWith(
      expect.objectContaining({ type: "message", text: "hello", thread_id: THREAD }),
    );
  });
});
