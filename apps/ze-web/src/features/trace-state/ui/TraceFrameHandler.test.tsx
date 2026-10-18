import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useConversation } from "@/entities/conversation";
import { useTraceStore } from "../model/useTraceStore";
import { TraceFrameHandler } from "./TraceFrameHandler";

vi.mock("../model/useTraceSocket", () => ({ useTraceSocket: () => undefined }));

const T = "t1";
const ctx = { activeThreadId: T };

describe("TraceFrameHandler", () => {
  beforeEach(() => {
    useConversation.setState({ byThread: {} });
    useTraceStore.setState({ byThread: {} });
  });

  it("starts each turn clean but keeps the pending trace when a confirmation resumes it", () => {
    render(<TraceFrameHandler />);
    useConversation.getState().apply({ type: "sent", threadId: T, text: "hi", context: undefined, workspacePlaced: false, resend: false } as never, ctx);
    useTraceStore.getState().mergePartialTrace({ thread_id: T, agent: "companion" } as never);
    expect(useTraceStore.getState().byThread[T].pendingTrace).not.toBeNull();
    useConversation.getState().apply({ type: "paused", threadId: T } as never, ctx);
    useConversation.getState().apply({ type: "resumed", threadId: T } as never, ctx);
    expect(useTraceStore.getState().byThread[T].pendingTrace).not.toBeNull();
  });
});
