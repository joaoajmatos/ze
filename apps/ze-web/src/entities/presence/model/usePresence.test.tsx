import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WsInboundFrame } from "@myguyze/ze-client";

type Handler = (f: WsInboundFrame) => void;
const handlers = new Map<string, Set<Handler>>();

vi.mock("@/shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api")>();
  const { useEffect, useRef } = await import("react");
  return {
    ...actual,
    useFrame: (type: string, handler: Handler) => {
      const ref = useRef(handler);
      ref.current = handler;
      useEffect(() => {
        const fn: Handler = (f) => ref.current(f);
        if (!handlers.has(type)) handlers.set(type, new Set());
        handlers.get(type)!.add(fn);
        return () => {
          handlers.get(type)?.delete(fn);
        };
      }, [type]);
    },
  };
});

import { useWsStore } from "@/shared/api";
import { usePresence } from "./usePresence";
import { usePresenceStore } from "./store";

function emit(frame: unknown) {
  const f = frame as WsInboundFrame;
  act(() => handlers.get(f.type)?.forEach((h) => h(f)));
}

const assistant = (thread: string | null) => ({ type: "message", message: { id: "m", role: "assistant", text: "hi", components: [], read: true, thread_id: thread, created_at: "x" } });

beforeEach(() => {
  vi.useFakeTimers();
  usePresenceStore.getState().reset();
  useWsStore.setState({ isConnected: true, thinkingThreads: {}, typingTextThreads: {} });
});
afterEach(() => {
  vi.useRealTimers();
  handlers.clear();
});

describe("usePresence", () => {
  it("is idle once connected, offline when the socket closes", () => {
    const { result } = renderHook(() => usePresence("t1"));
    expect(result.current.orb).toBe("idle");
    act(() => useWsStore.setState({ isConnected: false }));
    expect(result.current.orb).toBe("error");
    expect(result.current.phrase).toBe("Offline");
  });

  it("a replayed assistant message after connect leaves the orb idle", () => {
    const { result } = renderHook(() => usePresence("t1"));
    emit(assistant("t1"));
    expect(result.current.orb).toBe("idle");
  });

  it("ignores thinking and tokens for another thread, and tokens with a null thread", () => {
    const { result } = renderHook(() => usePresence("t1"));
    emit({ type: "typing", thread_id: "t2", text: "x" });
    emit({ type: "token", thread_id: "t2", text: "x" });
    emit({ type: "token", thread_id: null, text: "x" });
    expect(result.current.orb).toBe("idle");
  });

  it("follows typing, token and message on the active thread", () => {
    const { result } = renderHook(() => usePresence("t1"));
    emit({ type: "typing", thread_id: "t1", text: "Looking at your calendar" });
    expect(result.current.orb).toBe("thinking");
    expect(result.current.phrase).toBe("Looking at your calendar");
    emit({ type: "token", thread_id: "t1", text: "He" });
    expect(result.current.orb).toBe("speaking");
    emit(assistant("t1"));
    expect(result.current.orb).toBe("done");
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.orb).toBe("idle");
  });

  it("thinking from the per-thread store when the turn starts before any typing frame", () => {
    const { result } = renderHook(() => usePresence("t1"));
    act(() => useWsStore.setState({ thinkingThreads: { t1: true } }));
    expect(result.current.orb).toBe("thinking");
  });

  it("goes idle when the thread stops being busy with no closing frame (a confirmation is waiting)", () => {
    const { result } = renderHook(() => usePresence("t1"));
    act(() => useWsStore.setState({ thinkingThreads: { t1: true } }));
    expect(result.current.orb).toBe("thinking");
    act(() => useWsStore.setState({ thinkingThreads: { t1: false } }));
    expect(result.current.orb).toBe("idle");
  });

  it("keeps the done bloom when the busy flag falls after the message frame", () => {
    const { result } = renderHook(() => usePresence("t1"));
    act(() => useWsStore.setState({ thinkingThreads: { t1: true } }));
    emit(assistant("t1"));
    act(() => useWsStore.setState({ thinkingThreads: { t1: false } }));
    expect(result.current.orb).toBe("done");
  });

  it("an error frame for the thread returns to idle", () => {
    const { result } = renderHook(() => usePresence("t1"));
    emit({ type: "typing", thread_id: "t1" });
    emit({ type: "error", thread_id: "t1", detail: "boom" });
    expect(result.current.orb).toBe("idle");
  });

  it("derives no turn events with a null thread", () => {
    const { result } = renderHook(() => usePresence(null));
    emit({ type: "typing", thread_id: "t1" });
    emit({ type: "token", thread_id: "t1", text: "x" });
    expect(result.current.orb).toBe("idle");
  });

  it("drops the turn when the active thread changes", () => {
    const { result, rerender } = renderHook(({ id }) => usePresence(id), { initialProps: { id: "t1" as string | null } });
    emit({ type: "typing", thread_id: "t1" });
    expect(result.current.orb).toBe("thinking");
    rerender({ id: "t2" });
    expect(result.current.orb).toBe("idle");
  });
});
