import type { WsScreenContext } from "@myguyze/ze-client";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ send: vi.fn((_f: unknown) => true), notice: vi.fn() }));
vi.mock("@/shared/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/shared/api")>()), send: m.send }));
vi.mock("@/shared/lib", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/lib")>()),
  useSendNotice: { getState: () => ({ showNotice: m.notice }) },
}));
vi.mock("@/entities/screen-context", () => ({
  screenSnapshot: () => ({ route: "/doing", place: "doing", captured_at: "snap" }),
}));

import { useConversation } from "@/entities/conversation";
import { resendTurn, sendTurn } from "./useSendTurn";

const state = () => useConversation.getState().byThread.t1;

beforeEach(() => {
  m.send.mockReset();
  m.send.mockReturnValue(true);
  m.notice.mockReset();
  useConversation.setState({ byThread: {} });
});

describe("sendTurn", () => {
  it("merges the screen snapshot under the explicit context and the placed files", () => {
    const placed = [{ path: "a.txt", size: 3 }];
    expect(sendTurn("t1", "  hi  ", { explicitContext: { origin: "chat_about" } as WsScreenContext, workspacePlaced: placed })).toBe(true);
    expect(m.send).toHaveBeenCalledWith({
      type: "message",
      text: "hi",
      thread_id: "t1",
      context: { route: "/doing", place: "doing", captured_at: "snap", origin: "chat_about", workspace_placed: placed },
    });
    expect(state().turn.phase).toBe("awaiting");
    expect(state().turn.lastSent?.workspacePlaced).toEqual(placed);
  });

  it("sends a context that already carries captured_at as it was, without a new snapshot", () => {
    const own = { route: "/world", captured_at: "queued", compose: "slipping", origin: "preset" } as WsScreenContext;
    sendTurn("t1", "What's slipping?", { explicitContext: own });
    expect(m.send.mock.calls[0][0]).toMatchObject({ context: own });
  });

  it("refuses an empty text and a thread that is already running", () => {
    expect(sendTurn("t1", "   ")).toBe(false);
    expect(sendTurn("t1", "one")).toBe(true);
    expect(sendTurn("t1", "two")).toBe(false);
    expect(m.send).toHaveBeenCalledTimes(1);
  });

  it("returns false with the notice when offline and records nothing", () => {
    m.send.mockReturnValue(false);
    expect(sendTurn("t1", "hi")).toBe(false);
    expect(m.notice).toHaveBeenCalledWith("Not connected. Retry when Ze reconnects.");
    expect(state()).toBeUndefined();
  });

  it("resend replays the last context and keeps the original line", () => {
    sendTurn("t1", "hi", { explicitContext: { origin: "ask_bar" } as WsScreenContext });
    useConversation.getState().apply({ type: "delivery_failed", threadId: "t1" }, { activeThreadId: "t1" });
    expect(resendTurn("t1")).toBe(true);
    expect(m.send).toHaveBeenLastCalledWith({ type: "message", text: "hi", thread_id: "t1", context: expect.objectContaining({ origin: "ask_bar", captured_at: "snap" }) });
    expect(state().messages.filter((x) => x.role === "user")).toHaveLength(1);
    expect(state().turn.phase).toBe("awaiting");
  });
});
