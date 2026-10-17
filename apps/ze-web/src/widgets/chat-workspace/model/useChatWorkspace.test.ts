import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
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

const confirmState = vi.hoisted(() => ({
  pendingConfirms: [] as { id: string }[],
  respond: vi.fn(),
  clear: vi.fn(),
}));

vi.mock("@/features/respond-to-confirmation", () => ({
  useConfirmation: () => confirmState,
}));

import { useScreenContextStore } from "@/entities/screen-context";
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
    confirmState.pendingConfirms = [];
    confirmState.respond.mockReset();
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

  it("hands the pending confirmation and its responder to the widget", async () => {
    confirmState.pendingConfirms = [{ id: "req-1" }];
    const hook = setup();
    await flush();
    expect(hook.result.current.pendingConfirms).toEqual([{ id: "req-1" }]);
    hook.result.current.respondToConfirm("req-1", "approve", { c1: "edited" });
    expect(confirmState.respond).toHaveBeenCalledWith("req-1", "approve", { c1: "edited" });
  });

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

describe("useChatWorkspace recovery after a dropped socket", () => {
  beforeEach(() => {
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
      interruptedThreads: {},
    });
  });

  it("shows the retry state when reconnect finds no reply for an interrupted turn", async () => {
    const hook = setup();
    await flush();
    act(() => useWsStore.setState({ isConnected: false, interruptedThreads: { [THREAD]: true } }));
    act(() => useWsStore.setState({ isConnected: true }));
    await waitFor(() => expect(hook.result.current.deliveryFailed).toBe(true));
    expect(listMessagesMock).toHaveBeenCalled();
    expect(useWsStore.getState().interruptedThreads[THREAD]).toBeUndefined();
  });

  it("stays quiet when the stored reply is found after reconnect", async () => {
    const hook = setup();
    await flush();
    listMessagesMock.mockResolvedValue({ data: [message("a1", "assistant", "late reply")] });
    act(() => useWsStore.setState({ isConnected: false, interruptedThreads: { [THREAD]: true } }));
    act(() => useWsStore.setState({ isConnected: true }));
    await waitFor(() =>
      expect(hook.result.current.messages.map((m) => m.text)).toEqual(["late reply"]),
    );
    expect(hook.result.current.deliveryFailed).toBe(false);
  });

  it("unlocks and keeps the reply when a message lands for an inactive hook", async () => {
    const hook = setup({ active: false });
    await flush();
    act(() => useWsStore.getState().setThreadThinking(THREAD, true));

    act(() =>
      handlers.get("message")?.({ type: "message", message: message("a1", "assistant", "hi") }),
    );

    expect(hook.result.current.isThinking).toBe(false);
    expect(hook.result.current.messages.map((m) => m.text)).toEqual(["hi"]);
  });
});

describe("useChatWorkspace send path: the screen context", () => {
  beforeEach(() => {
    confirmState.pendingConfirms = [];
    handlers.clear();
    sendMock.mockClear();
    sendMock.mockReturnValue(true);
    listMessagesMock.mockReset();
    listMessagesMock.mockResolvedValue({ data: [] });
    useWsStore.setState({ isConnected: true, thinkingThreads: {}, typingTextThreads: {}, attentionThreads: {} });
    useScreenContextStore.getState().reset();
    window.history.pushState({}, "", "/doing/goals/g1");
    useScreenContextStore.getState().publish("page", { subject: [{ kind: "goal", id: "g1", label: "LedgerLite" }] });
  });
  afterEach(() => {
    useScreenContextStore.getState().reset();
    window.history.pushState({}, "", "/");
  });

  const sentContext = () => (sendMock.mock.calls.at(-1)?.[0] as { context: Record<string, unknown> }).context;

  it("sends the screen snapshot with every message", async () => {
    const { result } = setup();
    await flush();
    act(() => void result.current.sendMessage("what is blocking this?"));
    expect(sentContext()).toMatchObject({ place: "doing", route: "/doing/goals/g1", subject: [{ kind: "goal", id: "g1" }] });
    expect(typeof sentContext().captured_at).toBe("string");
  });

  it("explicit context goes over the snapshot", async () => {
    const { result } = setup({ context: { origin: "chat_about", subject: [{ kind: "workflow", id: "w1" }] } });
    await flush();
    act(() => void result.current.sendMessage("why?"));
    expect(sentContext()).toMatchObject({ origin: "chat_about", subject: [{ kind: "workflow", id: "w1" }], place: "doing" });
  });

  it("a finished snapshot (the overlay's queued item) is sent as it was, not mixed with the screen now", async () => {
    const queued = { place: "mind" as const, route: "/mind", captured_at: "2026-10-17T14:00:00Z" };
    const { result } = setup({ context: queued });
    await flush();
    act(() => void result.current.sendMessage("x"));
    expect(sentContext()).toEqual(queued);
  });

  it("a workspace upload merges workspace_placed into the context", async () => {
    const { result } = setup();
    await flush();
    act(() => void result.current.sendMessage("read this", [{ path: "a.txt", size: 4 }]));
    expect(sentContext()).toMatchObject({ workspace_placed: [{ path: "a.txt", size: 4 }], place: "doing" });
  });

  it("a preset context passes through with its origin", async () => {
    const { result } = setup({ context: { origin: "preset", compose: "slipping" } });
    await flush();
    act(() => void result.current.sendMessage("What's slipping?"));
    expect(sentContext()).toMatchObject({ origin: "preset", compose: "slipping", place: "doing" });
  });

  it("retry replays the context it sent, not the screen now", async () => {
    const { result } = setup();
    await flush();
    act(() => void result.current.sendMessage("first"));
    const original = sentContext();
    act(() => useWsStore.setState({ thinkingThreads: {} }));
    window.history.pushState({}, "", "/mind");
    useScreenContextStore.getState().reset();
    sendMock.mockClear();
    act(() => void result.current.retry());
    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(sentContext()).toEqual(original);
  });
});
