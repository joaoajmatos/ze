import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSendNotice } from "@/features/send-context-notice";
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
    useSendNotice.getState().clearNotice();
  });

  it("keeps the request's items, kind, round and expiry", () => {
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open();
    expect(result.current.pendingConfirm).toMatchObject({
      id: "req-1",
      kind: "write",
      round: 1,
      title: "Ze needs your OK",
      expiresAt: "2026-10-15T20:15:00Z",
      submitted: false,
    });
    expect(result.current.pendingConfirm?.items).toHaveLength(1);
  });

  it("sends confirm with the choice and the edits", () => {
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open();
    act(() => result.current.respond("approve", { c1: "new body" }));
    expect(sendMock).toHaveBeenCalledWith({
      type: "confirm",
      id: "req-1",
      choice: "approve",
      thread_id: THREAD,
      edits: { c1: "new body" },
    });
  });

  it("sends deny without edits", () => {
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open();
    act(() => result.current.respond("deny", {}));
    expect(sendMock).toHaveBeenCalledWith({
      type: "confirm",
      id: "req-1",
      choice: "deny",
      thread_id: THREAD,
    });
  });

  it("marks the card submitted until confirm_cancel arrives", () => {
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open();
    act(() => result.current.respond("approve", {}));
    expect(result.current.pendingConfirm?.submitted).toBe(true);
    expect(useWsStore.getState().thinkingThreads[THREAD]).toBe(true);
    act(() => handlers.get("confirm_cancel")?.({ type: "confirm_cancel", id: "req-1", thread_id: THREAD }));
    expect(result.current.pendingConfirm).toBeNull();
  });

  it("ignores a confirm_cancel for another request", () => {
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open();
    act(() => handlers.get("confirm_cancel")?.({ type: "confirm_cancel", id: "other", thread_id: THREAD }));
    expect(result.current.pendingConfirm?.id).toBe("req-1");
  });

  it("replaces the card when the next round arrives", () => {
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open();
    act(() => result.current.respond("approve", {}));
    open(requestFrame({ id: "req-2", round: 2 }));
    expect(result.current.pendingConfirm).toMatchObject({ id: "req-2", round: 2, submitted: false });
  });

  it("re-enables the card and shows a notice when the socket is down", () => {
    sendMock.mockReturnValue(false);
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open();
    act(() => result.current.respond("approve", {}));
    expect(result.current.pendingConfirm?.submitted).toBe(false);
    expect(useSendNotice.getState().notice).toMatch(/not connected/i);
  });

  it("flags attention instead of opening a card for another thread", () => {
    const { result } = renderHook(() => useConfirmation(true, false, THREAD));
    open(requestFrame({ thread_id: "thread-2" }));
    expect(result.current.pendingConfirm).toBeNull();
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
      const { result } = renderHook(() => useConfirmation(true, false, THREAD));
      open(promptFrame());
      expect(result.current.pendingConfirm).toMatchObject({
        id: "gate-1",
        kind: "prompt",
        title: "Milestone 2 is ready. Continue?",
        items: [],
        submitted: false,
      });
    });

    it("sends a non-checkpoint button as an action frame and closes the card", () => {
      const { result } = renderHook(() => useConfirmation(true, false, THREAD));
      open(promptFrame());
      act(() => result.current.respond("goal_gate:pause:abc"));
      expect(sendMock).toHaveBeenCalledWith({
        type: "action",
        payload: "goal_gate:pause:abc",
        thread_id: THREAD,
      });
      expect(result.current.pendingConfirm).toBeNull();
      expect(useWsStore.getState().thinkingThreads[THREAD]).toBeFalsy();
    });

    it("sends approve/deny on a prompt frame as a confirm frame and closes the card", () => {
      const { result } = renderHook(() => useConfirmation(true, false, THREAD));
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
      act(() => result.current.respond("deny"));
      expect(sendMock).toHaveBeenCalledWith({
        type: "confirm",
        id: "reset-1",
        choice: "deny",
        thread_id: THREAD,
      });
      expect(result.current.pendingConfirm).toBeNull();
    });

    it("restores the card and shows a notice when an action cannot be sent", () => {
      sendMock.mockReturnValue(false);
      const { result } = renderHook(() => useConfirmation(true, false, THREAD));
      open(promptFrame());
      act(() => result.current.respond("goal_gate:pause:abc"));
      expect(result.current.pendingConfirm?.id).toBe("gate-1");
      expect(useSendNotice.getState().notice).toMatch(/not connected/i);
    });
  });
});
