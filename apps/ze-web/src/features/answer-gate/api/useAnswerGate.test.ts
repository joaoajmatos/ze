import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnswerGateFrameHandler } from "../ui/AnswerGateFrameHandler";
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

// The shell mounts the handler once; the tests mount it beside the hook.
function useBoth(ids: readonly string[]) {
  AnswerGateFrameHandler();
  return useAnswerGate(ids);
}

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
    const { result } = renderHook(() => useBoth(["g1", "g2", "g3"]));
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
    const { result } = renderHook(() => useBoth(["g1"]));
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
    const { result, rerender } = renderHook(({ ids }) => useBoth(ids), { initialProps: { ids: ["g1"] } });
    act(() => void result.current.proceed("g1"));
    act(() => void vi.advanceTimersByTime(60_000));
    expect(result.current.stateOf("g1")).toBe("in_flight");
    rerender({ ids: [] });
    expect(result.current.stateOf("g1")).toBe("idle");
  });

  it("an error frame on the thread within 15 s clears the flight and returns the error", () => {
    const { result } = renderHook(() => useBoth(["g1"]));
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
    const { result } = renderHook(() => useBoth(["g1"]));
    act(() => void result.current.proceed("g1"));
    act(() => m.frames.error({ type: "error", thread_id: "other", detail: "x" }));
    expect(result.current.stateOf("g1")).toBe("in_flight");
    act(() => void vi.advanceTimersByTime(16_000));
    frame("error", { detail: "late" });
    expect(result.current.stateOf("g1")).toBe("in_flight");
  });

  it("Redirect is in flight only until the first message frame, then awaits instructions and Proceed still sends", () => {
    const { result } = renderHook(() => useBoth(["g1"]));
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
    const { result } = renderHook(() => useBoth(["g1"]));
    act(() => void result.current.redirect("g1"));
    frame("error", { detail: "nope" });
    expect(result.current.stateOf("g1")).toBe("idle");
    expect(result.current.errorOf("g1")).toBe("nope");
  });

  it("one error frame settles only the oldest answer still waiting, so two quick answers are not both re-enabled", () => {
    const { result } = renderHook(() => useBoth(["g1", "g2"]));
    act(() => void result.current.proceed("g1"));
    act(() => void vi.advanceTimersByTime(1_000));
    act(() => void result.current.proceed("g2"));
    frame("error", { detail: "boom" });
    expect(result.current.stateOf("g1")).toBe("idle");
    expect(result.current.errorOf("g1")).toBe("boom");
    expect(result.current.stateOf("g2")).toBe("in_flight");
  });

  it("returns false and records nothing when offline", () => {
    m.connected = false;
    m.send.mockReturnValue(false);
    const { result } = renderHook(() => useBoth(["g1"]));
    let sent = true;
    act(() => {
      sent = result.current.proceed("g1");
    });
    expect(sent).toBe(false);
    expect(result.current.stateOf("g1")).toBe("idle");
    expect(result.current.offline).toBe(true);
  });

  it("sends another payload family through the same sender", () => {
    const { result } = renderHook(() => useBoth([]));
    act(() => void result.current.answer("goal_stuck", "pause", "g9"));
    expect(m.send).toHaveBeenCalledWith({ type: "action", payload: "goal_stuck:pause:g9", thread_id: "t-1" });
  });
});

describe("useAnswerGate — stuck goals", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    m.send.mockReset();
    m.send.mockReturnValue(true);
    m.connected = true;
    useGateFlights.setState({ flights: {}, awaiting: {}, errors: {} });
  });
  afterEach(() => vi.useRealTimers());

  it("Pause stays in flight until the goals data no longer lists the goal as stuck", () => {
    const { result, rerender } = renderHook(({ ids }) => useBoth(ids), { initialProps: { ids: ["g9"] as readonly string[] } });
    act(() => void result.current.pause("g9"));
    expect(m.send).toHaveBeenCalledWith({ type: "action", payload: "goal_stuck:pause:g9", thread_id: "t-1" });
    expect(result.current.stateOf("g9")).toBe("in_flight");
    rerender({ ids: [] });
    expect(result.current.stateOf("g9")).toBe("idle");
  });

  it("Abandon asks once first, and sends only on the second call", () => {
    const { result } = renderHook(() => useBoth(["g9"]));
    act(() => void result.current.abandon("g9"));
    expect(m.send).not.toHaveBeenCalled();
    expect(result.current.abandonArmed("g9")).toBe(true);
    act(() => void result.current.abandon("g9"));
    expect(m.send).toHaveBeenCalledWith({ type: "action", payload: "goal_stuck:abandon:g9", thread_id: "t-1" });
    expect(result.current.abandonArmed("g9")).toBe(false);
  });

  it("cancelling the abandon question disarms it", () => {
    const { result } = renderHook(() => useBoth(["g9"]));
    act(() => void result.current.abandon("g9"));
    act(() => result.current.disarmAbandon("g9"));
    expect(result.current.abandonArmed("g9")).toBe(false);
  });

  it("Redirect on a stuck goal is in flight like a gate redirect and then awaits instructions", () => {
    const { result } = renderHook(() => useBoth(["g9"]));
    act(() => void result.current.redirectStuck("g9"));
    expect(m.send).toHaveBeenCalledWith({ type: "action", payload: "goal_stuck:redirect:g9", thread_id: "t-1" });
    frame("message");
    expect(result.current.stateOf("g9")).toBe("awaiting_instructions");
  });

  it("a flight with no refresh or error within 15 s ends with a timeout line", () => {
    const { result } = renderHook(() => useBoth(["g9"]));
    act(() => void result.current.pause("g9"));
    act(() => void vi.advanceTimersByTime(15_100));
    expect(result.current.stateOf("g9")).toBe("idle");
    expect(result.current.errorOf("g9")).toMatch(/hasn't answered/i);
  });

  it("the in-flight signal is the backend's refresh frame for goals, which refetches the goals key", async () => {
    const { refreshKeysForScreen, queryKeys } = await import("@/shared/lib");
    expect(refreshKeysForScreen("goals")).toContainEqual(queryKeys.goals);
  });

  it("no path in the feature calls startGoal", async () => {
    const { readFileSync, readdirSync } = await import("node:fs");
    const { join } = await import("node:path");
    const root = join(__dirname, "..");
    const files = ["api/useAnswerGate.ts", "ui/AnswerGateFrameHandler.tsx", "model/gate-flights.ts", ...readdirSync(root).filter((f) => f === "index.ts")];
    for (const f of files) expect(readFileSync(join(root, f), "utf8")).not.toMatch(/startGoal/);
  });
});
