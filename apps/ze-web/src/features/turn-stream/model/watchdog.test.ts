import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { emptyThread, useConversation } from "@/entities/conversation";
import { useWsStore } from "@/shared/api";
import { DELIVERY_WATCHDOG_MS, startDeliveryWatchdog } from "./watchdog";

const T = "t1";
const apply = (e: Parameters<ReturnType<typeof useConversation.getState>["apply"]>[0]) =>
  useConversation.getState().apply(e, { activeThreadId: T });
const phase = () => useConversation.getState().byThread[T]?.turn.phase;
const send = () => apply({ type: "sent", threadId: T, text: "hi", context: {} });

let stop: () => void;
let reload: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(1_000_000);
  useConversation.setState({ byThread: { [T]: emptyThread() } });
  useWsStore.setState({ isConnected: true, interruptedThreads: {} });
  reload = vi.fn(async () => null);
  stop = startDeliveryWatchdog({ reload });
});
afterEach(() => {
  stop();
  vi.useRealTimers();
});

describe("delivery watchdog", () => {
  it("after 120 s of silence reloads history and fails the turn when no reply came", async () => {
    send();
    await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS);
    expect(reload).toHaveBeenCalledWith(T);
    expect(phase()).toBe("failed");
  });

  it("leaves the turn alone when the reload finds the reply", async () => {
    reload.mockImplementation(async () => {
      apply({ type: "history_loaded", threadId: T, messages: [{ id: "r", role: "assistant", text: "x", components: [], read: true, thread_id: T, created_at: "2026-10-18T10:00:00Z" }] });
      return null;
    });
    send();
    await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS);
    expect(phase()).toBe("idle");
  });

  it("is pushed back by activity", async () => {
    send();
    await vi.advanceTimersByTimeAsync(100_000);
    apply({ type: "typing", thread_id: T, text: "x" });
    await vi.advanceTimersByTimeAsync(100_000);
    expect(reload).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(20_000);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("never fails a turn paused on a confirmation, and restarts when it resumes", async () => {
    send();
    apply({ type: "paused", threadId: T });
    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(reload).not.toHaveBeenCalled();
    expect(phase()).toBe("paused");
    apply({ type: "resumed", threadId: T });
    await vi.advanceTimersByTimeAsync(DELIVERY_WATCHDOG_MS);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("checks an interrupted thread on reconnect", async () => {
    send();
    useWsStore.setState({ isConnected: false, interruptedThreads: { [T]: true } });
    useWsStore.setState({ isConnected: true });
    await vi.advanceTimersByTimeAsync(0);
    expect(reload).toHaveBeenCalledWith(T);
    expect(useWsStore.getState().interruptedThreads[T]).toBeUndefined();
    expect(phase()).toBe("failed");
  });
});
