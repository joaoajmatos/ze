import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
import type { WsInboundFrame } from "@myguyze/ze-client";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Handler = (f: WsInboundFrame) => void;
const handlers = new Map<string, Set<Handler>>();
const sendMock = vi.hoisted(() => vi.fn(() => true));

vi.mock("@/shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api")>();
  const { useEffect, useRef } = await import("react");
  return {
    ...actual,
    send: sendMock,
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

import { useConversation } from "@/entities/conversation";
import { useOnboardingSession } from "@/entities/onboarding-session";
import { usePresenceStore } from "@/entities/presence";
import { useSession } from "@/entities/session";
import { useWsStore } from "@/shared/api";
import { TurnFrameHandler } from "./TurnFrameHandler";

const realApply = useConversation.getState().apply;

const emit = (frame: unknown) => {
  const f = frame as WsInboundFrame;
  act(() => handlers.get(f.type)?.forEach((h) => h(f)));
};
const assistant = (thread: string | null, over = {}) => ({
  type: "message",
  message: { id: "m1", role: "assistant", text: "hi", components: [], read: false, thread_id: thread, created_at: "2026-10-18T10:00:00Z", ...over },
});
let qc: QueryClient;
const wrap = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
const mount = () => render(<TurnFrameHandler />, { wrapper: wrap });
const thread = (id = "t1") => useConversation.getState().byThread[id];
const confirmFrame = (over = {}) => ({ type: "confirm_request", id: "c1", thread_id: "t1", kind: "write", title: "x", items: [], actions: [], ...over });

beforeEach(() => {
  vi.useFakeTimers();
  qc = new QueryClient();
  vi.spyOn(qc, "invalidateQueries");
  useConversation.setState({ byThread: {}, apply: realApply });
  useSession.setState({ threadId: "t1" });
  usePresenceStore.getState().reset();
  useWsStore.setState({ isConnected: true, thinkingThreads: {}, typingTextThreads: {}, attentionThreads: {} });
  sendMock.mockClear();
});
afterEach(() => {
  vi.useRealTimers();
  handlers.clear();
});

describe("TurnFrameHandler", () => {
  it("routes each of the seven conversation frames to the reducer once", () => {
    const apply = vi.fn();
    useConversation.setState({ apply });
    mount();
    emit({ type: "typing", thread_id: "t1", text: "x" });
    emit({ type: "token", thread_id: "t1", text: "x" });
    emit(assistant("t1"));
    emit({ type: "edit", id: "m1", thread_id: "t1", text: "y" });
    emit({ type: "error", thread_id: "t1", detail: "d" });
    emit({ type: "message_superseded", thread_id: "t1", message_id: "a", replaced_by: "b" });
    emit({ type: "message_rollback", thread_id: "t1", message_id: "a", rollback: { state: "partial", entries: [] } });
    const types = apply.mock.calls.map((c) => c[0].type).filter((t) => t !== "opened");
    expect(types).toEqual(["typing", "token", "message", "edit", "error", "message_superseded", "message_rollback"]);
  });

  it("pauses a busy thread on confirm_request but not a held write", () => {
    mount();
    emit({ type: "typing", thread_id: "t1", text: "x" });
    emit(confirmFrame({ kind: "held", thread_id: null }));
    expect(thread().turn.phase).toBe("thinking");
    emit(confirmFrame());
    expect(thread().turn.phase).toBe("paused");
  });

  it("keeps the ws thinking, typing and attention flags in step with the store", () => {
    mount();
    emit({ type: "typing", thread_id: "t2", text: "working" });
    expect(useWsStore.getState().thinkingThreads.t2).toBe(true);
    expect(useWsStore.getState().typingTextThreads.t2).toBe("working");
    emit(assistant("t2", { id: "r" }));
    expect(useWsStore.getState().thinkingThreads.t2).toBe(false);
    expect(useWsStore.getState().attentionThreads.t2).toBe(true);
  });

  it("acks an unread assistant reply of the active thread only", () => {
    mount();
    emit(assistant("t2", { id: "other" }));
    expect(sendMock).not.toHaveBeenCalled();
    emit(assistant("t1", { id: "mine" }));
    expect(sendMock).toHaveBeenCalledWith({ type: "ack", ids: ["mine"] });
  });

  it("dispatches presence events for the active thread only", () => {
    mount();
    emit({ type: "typing", thread_id: "t2", text: "x" });
    expect(usePresenceStore.getState().presence.turn).toBe("none");
    emit({ type: "typing", thread_id: "t1", text: "looking" });
    expect(usePresenceStore.getState().presence.turn).toBe("thinking");
    emit({ type: "token", thread_id: "t1", text: "a" });
    expect(usePresenceStore.getState().presence.turn).toBe("speaking");
  });

  it("invalidates sessions debounced on typing and at once on an assistant message", () => {
    mount();
    emit({ type: "typing", thread_id: "t1" });
    emit({ type: "typing", thread_id: "t1" });
    expect(qc.invalidateQueries).not.toHaveBeenCalled();
    act(() => void vi.advanceTimersByTime(2100));
    expect(qc.invalidateQueries).toHaveBeenCalledTimes(1);
    emit(assistant("t1"));
    expect(qc.invalidateQueries).toHaveBeenCalledTimes(2);
  });

  it("updates the onboarding session from a message frame", () => {
    mount();
    emit({ ...assistant("onboarding:s1"), onboarding: { session_id: "s1", completed: false } });
    expect(useOnboardingSession.getState().sessionId).toBe("s1");
  });
});
