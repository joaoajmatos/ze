import { act, renderHook as baseRenderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSession } from "@/entities/session";
import { useSendNotice } from "@/shared/lib";
import { usePendingConfirms } from "../model/pending-store";
import { ConfirmationFrameHandler } from "../ui/ConfirmationFrameHandler";
import { useConfirmation } from "./useConfirmation";

type Handler = (frame: Record<string, unknown>) => void;
const handlers = new Map<string, Handler>();
const sendMock = vi.fn((_frame: unknown) => true);

vi.mock("@/shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api")>()),
  send: (frame: unknown) => sendMock(frame),
  useFrame: (type: string, handler: Handler) => {
    handlers.set(type, handler);
  },
}));

import { useWsStore } from "@/shared/api";

const THREAD = "thread-1";

function renderHook<T, P = undefined>(fn: (props: P) => T, options?: { initialProps?: P }) {
  return baseRenderHook(fn, {
    ...options,
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement("div", null, createElement(ConfirmationFrameHandler), children),
  });
}

function requestFrame(overrides: Record<string, unknown> = {}) {
  return {
    type: "confirm_request",
    id: "req-1",
    thread_id: THREAD,
    kind: "write",
    round: 1,
    title: "Ze needs your OK",
    items: [
      {
        item_id: "c1",
        agent: "calendar",
        tool: "delete_event",
        effect_phrase: "delete a calendar event",
        summary: "Dentist — today 15:00",
        conflict: null,
        editable_field: null,
        proposed_text: null,
      },
    ],
    source: null,
    expires_at: "2026-10-15T20:15:00Z",
    actions: [
      { label: "Approve all", value: "approve", style: "primary" },
      { label: "Deny all", value: "deny", style: "secondary" },
    ],
    ...overrides,
  };
}

function open(frame: Record<string, unknown> = requestFrame()) {
  act(() => handlers.get("confirm_request")?.(frame));
}

describe("useConfirmation", () => {
  beforeEach(() => {
    handlers.clear();
    sendMock.mockReset();
    sendMock.mockReturnValue(true);
    useWsStore.setState({ thinkingThreads: {} });
    usePendingConfirms.setState({ byThread: {} });
    useSession.setState({ threadId: THREAD });
    useSendNotice.getState().clearNotice();
  });

  it("keeps the request's items, kind, round and expiry", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    expect(result.current.pendingConfirms[0]).toMatchObject({
      id: "req-1",
      kind: "write",
      round: 1,
      title: "Ze needs your OK",
      expiresAt: "2026-10-15T20:15:00Z",
      submitted: false,
    });
    expect(result.current.pendingConfirms[0]?.items).toHaveLength(1);
  });

  it("sends confirm with the choice and the edits", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    act(() => result.current.respond("req-1", "approve", { c1: "new body" }));
    expect(sendMock).toHaveBeenCalledWith({
      type: "confirm",
      id: "req-1",
      choice: "approve",
      thread_id: THREAD,
      edits: { c1: "new body" },
    });
  });

  it("sends deny without edits", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    act(() => result.current.respond("req-1", "deny", {}));
    expect(sendMock).toHaveBeenCalledWith({
      type: "confirm",
      id: "req-1",
      choice: "deny",
      thread_id: THREAD,
    });
  });

  it("marks the card submitted until confirm_cancel arrives", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    act(() => result.current.respond("req-1", "approve", {}));
    expect(result.current.pendingConfirms[0]?.submitted).toBe(true);
    expect(useWsStore.getState().thinkingThreads[THREAD]).toBe(true);
    act(() => handlers.get("confirm_cancel")?.({ type: "confirm_cancel", id: "req-1", thread_id: THREAD }));
    expect(result.current.pendingConfirms).toEqual([]);
  });

  it("ignores a confirm_cancel for another request", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    act(() => handlers.get("confirm_cancel")?.({ type: "confirm_cancel", id: "other", thread_id: THREAD }));
    expect(result.current.pendingConfirms[0]?.id).toBe("req-1");
  });

  it("replaces the card when the next round arrives", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    act(() => result.current.respond("req-1", "approve", {}));
    open(requestFrame({ id: "req-2", round: 2 }));
    expect(result.current.pendingConfirms[0]).toMatchObject({ id: "req-2", round: 2, submitted: false });
  });

  it("re-enables the card and shows a notice when the socket is down", () => {
    sendMock.mockReturnValue(false);
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    act(() => result.current.respond("req-1", "approve", {}));
    expect(result.current.pendingConfirms[0]?.submitted).toBe(false);
    expect(useSendNotice.getState().notice).toMatch(/not connected/i);
  });

  it("flags attention instead of opening a card for another thread", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open(requestFrame({ thread_id: "thread-2" }));
    expect(result.current.pendingConfirms).toEqual([]);
  });

  it("keeps a request for another thread and shows it once that thread opens", () => {
    const { result, rerender } = renderHook(({ thread }) => useConfirmation(false, thread), {
      initialProps: { thread: THREAD },
    });
    open(requestFrame({ id: "req-t2", thread_id: "thread-2" }));
    expect(result.current.pendingConfirms).toEqual([]);
    expect(useWsStore.getState().attentionThreads["thread-2"]).toBe(true);
    rerender({ thread: "thread-2" });
    expect(result.current.pendingConfirms[0]).toMatchObject({ id: "req-t2", threadId: "thread-2" });
  });

  it("keeps a write confirmation open when a prompt frame arrives on the same thread", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    open(requestFrame({ id: "gate-1", kind: "prompt", items: [], title: "Continue?" }));
    expect(result.current.pendingConfirms.map((c) => c.id)).toEqual(["req-1", "gate-1"]);
    act(() => result.current.respond("req-1", "approve", {}));
    expect(sendMock).toHaveBeenCalledWith(expect.objectContaining({ id: "req-1", choice: "approve" }));
    expect(result.current.pendingConfirms.map((c) => c.id)).toEqual(["req-1", "gate-1"]);
  });

  it("cancels by request id even when the cancel frame names no thread", () => {
    const { result, rerender } = renderHook(({ thread }) => useConfirmation(false, thread), {
      initialProps: { thread: THREAD },
    });
    open(requestFrame({ id: "req-t2", thread_id: "thread-2" }));
    act(() => handlers.get("confirm_cancel")?.({ type: "confirm_cancel", id: "req-t2" }));
    rerender({ thread: "thread-2" });
    expect(result.current.pendingConfirms).toEqual([]);
  });

  it("cancels by request id when the cancel frame names the wrong thread", () => {
    const { result } = renderHook(() => useConfirmation(false, THREAD));
    open();
    act(() =>
      handlers.get("confirm_cancel")?.({ type: "confirm_cancel", id: "req-1", thread_id: "thread-9" }),
    );
    expect(result.current.pendingConfirms).toEqual([]);
  });

  describe("acknowledging an answer without a confirm_cancel", () => {
    it.each(["typing", "token"])("clears the answered card on the next %s frame", (type) => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open();
      act(() => result.current.respond("req-1", "approve", {}));
      expect(result.current.pendingConfirms[0]?.submitted).toBe(true);
      act(() => handlers.get(type)?.({ type, thread_id: THREAD }));
      expect(result.current.pendingConfirms).toEqual([]);
    });

    it("clears the answered card when the reply message arrives", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open();
      act(() => result.current.respond("req-1", "deny", {}));
      act(() => handlers.get("message")?.({ type: "message", message: { thread_id: THREAD } }));
      expect(result.current.pendingConfirms).toEqual([]);
    });

    it("leaves an unanswered card alone", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open();
      act(() => handlers.get("typing")?.({ type: "typing", thread_id: THREAD }));
      expect(result.current.pendingConfirms).toHaveLength(1);
    });

    it("does not clear another thread's answered card", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open();
      act(() => result.current.respond("req-1", "approve", {}));
      act(() => handlers.get("typing")?.({ type: "typing", thread_id: "thread-2" }));
      expect(result.current.pendingConfirms).toHaveLength(1);
    });
  });

  describe("held frames (no thread)", () => {
    const held = () => requestFrame({ id: "held-1", thread_id: null, kind: "held", source: { kind: "workflow", name: "Weekly" } });

    it("shows a held write on whichever thread is open", () => {
      const { result, rerender } = renderHook(({ thread }) => useConfirmation(false, thread), {
        initialProps: { thread: THREAD },
      });
      open(held());
      expect(result.current.pendingConfirms.map((c) => c.id)).toEqual(["held-1"]);
      rerender({ thread: "thread-2" });
      expect(result.current.pendingConfirms.map((c) => c.id)).toEqual(["held-1"]);
    });

    it("answers on the open thread and closes at once", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open(held());
      act(() => result.current.respond("held-1", "approve", {}));
      expect(sendMock).toHaveBeenCalledWith({ type: "confirm", id: "held-1", choice: "approve", thread_id: THREAD, edits: {} });
      expect(result.current.pendingConfirms).toEqual([]);
      expect(useWsStore.getState().thinkingThreads[THREAD]).toBeFalsy();
    });

    it("lists it beside the thread's own confirmation", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open(held());
      open(requestFrame({ id: "req-1" }));
      expect(result.current.pendingConfirms.map((c) => c.id).sort()).toEqual(["held-1", "req-1"]);
    });
  });

  describe("prompt frames (kind \"prompt\", no items)", () => {
    function promptFrame(overrides: Record<string, unknown> = {}) {
      return {
        type: "confirm_request",
        id: "gate-1",
        thread_id: THREAD,
        kind: "prompt",
        round: 1,
        title: "Milestone 2 is ready. Continue?",
        items: [],
        source: null,
        expires_at: null,
        actions: [
          { label: "Continue", value: "goal_gate:approve:abc", style: "primary" },
          { label: "Pause", value: "goal_gate:pause:abc", style: "secondary" },
        ],
        ...overrides,
      };
    }

    it("opens a card from the prompt without throwing", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open(promptFrame());
      expect(result.current.pendingConfirms[0]).toMatchObject({
        id: "gate-1",
        kind: "prompt",
        title: "Milestone 2 is ready. Continue?",
        items: [],
        submitted: false,
      });
    });

    it("sends a non-checkpoint button as an action frame and closes the card", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open(promptFrame());
      act(() => result.current.respond("gate-1", "goal_gate:pause:abc"));
      expect(sendMock).toHaveBeenCalledWith({
        type: "action",
        payload: "goal_gate:pause:abc",
        thread_id: THREAD,
      });
      expect(result.current.pendingConfirms).toEqual([]);
      expect(useWsStore.getState().thinkingThreads[THREAD]).toBeFalsy();
    });

    it("sends approve/deny on a prompt frame as a confirm frame and closes the card", () => {
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open(
        promptFrame({
          id: "reset-1",
          title: "Reset workspace?",
          actions: [
            { label: "Approve", value: "approve", style: "primary" },
            { label: "Cancel", value: "deny", style: "secondary" },
          ],
        }),
      );
      act(() => result.current.respond("reset-1", "deny"));
      expect(sendMock).toHaveBeenCalledWith({
        type: "confirm",
        id: "reset-1",
        choice: "deny",
        thread_id: THREAD,
      });
      expect(result.current.pendingConfirms).toEqual([]);
    });

    it("restores the card and shows a notice when an action cannot be sent", () => {
      sendMock.mockReturnValue(false);
      const { result } = renderHook(() => useConfirmation(false, THREAD));
      open(promptFrame());
      act(() => result.current.respond("gate-1", "goal_gate:pause:abc"));
      expect(result.current.pendingConfirms[0]?.id).toBe("gate-1");
      expect(useSendNotice.getState().notice).toMatch(/not connected/i);
    });
  });
});
