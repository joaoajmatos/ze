import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWsStore } from "@/shared/api";
import { usePresence } from "./usePresence";
import { usePresenceStore } from "./store";

// Turn events come from features/turn-stream; these tests dispatch them as it does.
const dispatch = (e: Parameters<ReturnType<typeof usePresenceStore.getState>["dispatch"]>[0]) =>
  act(() => usePresenceStore.getState().dispatch(e));

beforeEach(() => {
  vi.useFakeTimers();
  usePresenceStore.getState().reset();
  useWsStore.setState({ isConnected: true, displaced: false, thinkingThreads: {}, typingTextThreads: {} });
});
afterEach(() => vi.useRealTimers());

describe("usePresence", () => {
  it("is idle once connected, offline when the socket closes", () => {
    const { result } = renderHook(() => usePresence("t1"));
    expect(result.current.orb).toBe("idle");
    act(() => useWsStore.setState({ isConnected: false }));
    expect(result.current.orb).toBe("error");
    expect(result.current.phrase).toBe("Offline");
  });

  it("a message event with no turn running leaves the orb idle", () => {
    const { result } = renderHook(() => usePresence("t1"));
    dispatch({ type: "turn_message" });
    expect(result.current.orb).toBe("idle");
  });

  it("follows thinking, token and message", () => {
    const { result } = renderHook(() => usePresence("t1"));
    dispatch({ type: "turn_thinking", text: "Looking at your calendar" });
    expect(result.current.orb).toBe("thinking");
    expect(result.current.phrase).toBe("Looking at your calendar");
    dispatch({ type: "turn_token" });
    expect(result.current.orb).toBe("speaking");
    dispatch({ type: "turn_message" });
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

  it("keeps the done bloom when the busy flag falls after the message event", () => {
    const { result } = renderHook(() => usePresence("t1"));
    act(() => useWsStore.setState({ thinkingThreads: { t1: true } }));
    dispatch({ type: "turn_message" });
    act(() => useWsStore.setState({ thinkingThreads: { t1: false } }));
    expect(result.current.orb).toBe("done");
  });

  it("drops the turn when the active thread changes", () => {
    const { result, rerender } = renderHook(({ id }) => usePresence(id), { initialProps: { id: "t1" as string | null } });
    dispatch({ type: "turn_thinking" });
    expect(result.current.orb).toBe("thinking");
    rerender({ id: "t2" });
    expect(result.current.orb).toBe("idle");
  });

  it("rests, not Offline, while another window has the connection", () => {
    const { result } = renderHook(() => usePresence("t1"));
    act(() => useWsStore.setState({ isConnected: false, displaced: true }));
    expect(result.current.orb).toBe("idle");
    expect(result.current.phrase).not.toBe("Offline");
    act(() => useWsStore.setState({ displaced: false }));
    expect(result.current.orb).toBe("error");
  });
});
