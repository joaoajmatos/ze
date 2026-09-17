import { describe, it, expect, beforeEach, vi } from "vitest";
import { useSession } from "./session-store";

const reconnect = vi.fn();

vi.mock("@/shared/api", () => ({
  reconnect,
}));

describe("session-store highlight message", () => {
  beforeEach(() => {
    reconnect.mockClear();
    useSession.setState({ highlightMessageId: null });
  });

  it("setHighlightMessage sets the highlight target", () => {
    useSession.getState().setHighlightMessage("msg-1");
    expect(useSession.getState().highlightMessageId).toBe("msg-1");
  });

  it("selectSession switches the active thread without reconnecting the socket", () => {
    useSession.getState().selectSession("sess-99");
    expect(useSession.getState().threadId).toBe("sess-99");
    expect(reconnect).not.toHaveBeenCalled();
  });

  it("setHighlightMessage(null) clears the highlight", () => {
    useSession.getState().setHighlightMessage("msg-1");
    useSession.getState().setHighlightMessage(null);
    expect(useSession.getState().highlightMessageId).toBeNull();
  });
});
