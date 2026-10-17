import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAnswerGate } from "./useAnswerGate";
import { useGateFlights } from "../model/gate-flights";

const m = vi.hoisted(() => ({
  send: vi.fn(),
  connected: true,
  frames: {} as Record<string, (f: unknown) => void>,
}));

vi.mock("@/shared/api", () => ({
  send: m.send,
  useFrame: (type: string, handler: (f: unknown) => void) => {
    m.frames[type] = handler;
  },
  useWsStore: (sel: (s: { isConnected: boolean }) => unknown) => sel({ isConnected: m.connected }),
}));
vi.mock("@/entities/session", () => ({
  useSession: (sel: (s: { threadId: string }) => unknown) => sel({ threadId: "t-1" }),
}));

const frame = (type: string, extra: Record<string, unknown> = {}) =>
  act(() => m.frames[type](type === "message" ? { type, message: { thread_id: "t-1", ...extra } } : { type, thread_id: "t-1", ...extra }));

describe("useAnswerGate", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    m.send.mockReset();
    m.send.mockReturnValue(true);
    m.connected = true;
    useGateFlights.setState({ flights: {}, awaiting: {}, errors: {} });
  });
  afterEach(() => vi.useRealTimers());

  it("Proceed, Stop and Redirect send the action frame on the session thread", () => {
    const { result } = renderHook(() => useAnswerGate(["g1", "g2", "g3"]));
    act(() => void result.current.proceed("g1"));
    act(() => void result.current.stop("g2"));
    act(() => void result.current.redirect("g3"));
    expect(m.send.mock.calls.map((c) => c[0])).toEqual([
      { type: "action", payload: "goal:approve:g1", thread_id: "t-1" },
      { type: "action", payload: "goal:stop:g2", thread_id: "t-1" },
      { type: "action", payload: "goal:redirect:g3", thread_id: "t-1" },
    ]);
  });

  it("refuses a second Proceed or Stop for the same gate while in flight", () => {
    const { result } = renderHook(() => useAnswerGate(["g1"]));
    let first = false;
    let second = true;
    act(() => {
      first = result.current.proceed("g1");
    });
    act(() => {
      second = result.current.stop("g1");
    });
    expect(first).toBe(true);
    expect(second).toBe(false);
    expect(m.send).toHaveBeenCalledTimes(1);
    expect(result.current.stateOf("g1")).toBe("in_flight");
  });

  it("stays in flight until the goals data drops the gate", () => {
    const { result, rerender } = renderHook(({ ids }) => useAnswerGate(ids), { initialProps: { ids: ["g1"] } });
    act(() => void result.current.proceed("g1"));
    act(() => void vi.advanceTimersByTime(60_000));
    expect(result.current.stateOf("g1")).toBe("in_flight");
    rerender({ ids: [] });
    expect(result.current.stateOf("g1")).toBe("idle");
  });

  it("an error frame on the thread within 15 s clears the flight and returns the error", () => {
    const { result } = renderHook(() => useAnswerGate(["g1"]));
    act(() => void result.current.proceed("g1"));
    act(() => void vi.advanceTimersByTime(5_000));
    frame("error", { detail: "Checkpoint not found." });
    expect(result.current.stateOf("g1")).toBe("idle");
    expect(result.current.errorOf("g1")).toBe("Checkpoint not found.");
    let again = false;
    act(() => {
      again = result.current.proceed("g1");
    });
    expect(again).toBe(true);
    expect(result.current.errorOf("g1")).toBeNull();
  });

  it("ignores an error frame after 15 s, and one from another thread", () => {
    const { result } = renderHook(() => useAnswerGate(["g1"]));
    act(() => void result.current.proceed("g1"));
    act(() => m.frames.error({ type: "error", thread_id: "other", detail: "x" }));
    expect(result.current.stateOf("g1")).toBe("in_flight");
    act(() => void vi.advanceTimersByTime(16_000));
    frame("error", { detail: "late" });
    expect(result.current.stateOf("g1")).toBe("in_flight");
  });

  it("Redirect is in flight only until the first message frame, then awaits instructions and Proceed still sends", () => {
    const { result } = renderHook(() => useAnswerGate(["g1"]));
    act(() => void result.current.redirect("g1"));
    expect(result.current.stateOf("g1")).toBe("in_flight");
    frame("message", { text: "Send your instructions" });
    expect(result.current.stateOf("g1")).toBe("awaiting_instructions");
    let proceeded = false;
    act(() => {
      proceeded = result.current.proceed("g1");
    });
    expect(proceeded).toBe(true);
    expect(m.send).toHaveBeenLastCalledWith({ type: "action", payload: "goal:approve:g1", thread_id: "t-1" });
    expect(result.current.stateOf("g1")).toBe("in_flight");
  });

  it("Redirect ends on an error frame with the error", () => {
    const { result } = renderHook(() => useAnswerGate(["g1"]));
    act(() => void result.current.redirect("g1"));
    frame("error", { detail: "nope" });
    expect(result.current.stateOf("g1")).toBe("idle");
    expect(result.current.errorOf("g1")).toBe("nope");
  });

  it("returns false and records nothing when offline", () => {
    m.connected = false;
    m.send.mockReturnValue(false);
    const { result } = renderHook(() => useAnswerGate(["g1"]));
    let sent = true;
    act(() => {
      sent = result.current.proceed("g1");
    });
    expect(sent).toBe(false);
    expect(result.current.stateOf("g1")).toBe("idle");
    expect(result.current.offline).toBe(true);
  });

  it("sends another payload family through the same sender", () => {
    const { result } = renderHook(() => useAnswerGate([]));
    act(() => void result.current.answer("goal_stuck", "pause", "g9"));
    expect(m.send).toHaveBeenCalledWith({ type: "action", payload: "goal_stuck:pause:g9", thread_id: "t-1" });
  });
});
