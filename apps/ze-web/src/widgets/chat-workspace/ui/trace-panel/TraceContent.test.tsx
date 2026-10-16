import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { useTraceStore } from "@/features/trace-state";
import { TraceContent } from "./TraceContent";

vi.mock("@/features/trace-state", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/trace-state")>();
  return {
    ...actual,
    useTraceSocket: () => undefined,
    useSessionTraces: () => false,
  };
});

const { feedbackById } = vi.hoisted(() => ({ feedbackById: new Map<string, unknown>() }));
vi.mock("@/entities/message-feedback", () => ({
  useMessageFeedbackQuery: () => ({ byId: feedbackById, isLoading: false }),
}));

function frame(
  threadId: string,
  messageId: string,
  agent: string,
  ledgerAgent: string,
): WsTraceUpdateFrame {
  return {
    type: "trace_update",
    thread_id: threadId,
    message_id: messageId,
    agent,
    routing_method: "haiku",
    confidence: 0.8,
    score_gap: 0.1,
    is_compound: true,
    subtasks: [ledgerAgent],
    memory_chunks: [],
    tool_calls: [],
    total_duration_ms: 10,
    skills_used: [],
    conductor_hint: [{ agent: ledgerAgent, intent: "read", prompt: "go" }],
    conductor_ledger: [{ agent: ledgerAgent, status: "running" }],
  };
}

describe("TraceContent untraced feedback", () => {
  beforeEach(() => feedbackById.clear());

  it("lists a rated reply with no trace, marked as such (US5-5)", () => {
    useTraceStore.setState({
      byThread: {
        "thread-a": { traces: [], pending: false, pendingTrace: null, hydrating: false },
      },
    });
    feedbackById.set("msg-old", {
      message_id: "msg-old",
      current: "down",
      history: [{ kind: "thumbs_down", occurred_at: "2026-10-09T10:00:00Z" }],
      retry: { available: false, reason_code: "trace_unavailable", reason_text: "x" },
      replaces: null,
      replaced_by: null,
      trace_present: false,
    });
    render(<TraceContent threadId="thread-a" assistantMessageIds={["msg-old"]} />);
    expect(screen.getByTestId("untraced-feedback")).toHaveTextContent(/no trace recorded/i);
    expect(screen.getByTestId("feedback-current")).toHaveTextContent("Thumbs down");
  });
});

describe("TraceContent active session", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    useTraceStore.setState({
      byThread: {
        "thread-a": {
          traces: [frame("thread-a", "msg-a", "companion", "research")],
          pending: false,
          pendingTrace: null,
          hydrating: false,
        },
        "thread-b": {
          traces: [frame("thread-b", "msg-b", "companion", "calendar")],
          pending: false,
          pendingTrace: null,
          hydrating: false,
        },
      },
    });
  });

  it("shows only the active thread conductor ledger", () => {
    render(<TraceContent threadId="thread-a" assistantMessageIds={["msg-a"]} />);
    expect(screen.getAllByText("research").length).toBeGreaterThan(0);
    expect(screen.queryByText("calendar")).not.toBeInTheDocument();
  });

  it("switches the panel to the selected thread trace", () => {
    const { rerender } = render(
      <TraceContent threadId="thread-a" assistantMessageIds={["msg-a"]} />,
    );
    rerender(<TraceContent threadId="thread-b" assistantMessageIds={["msg-b"]} />);
    expect(screen.getAllByText("calendar").length).toBeGreaterThan(0);
    expect(screen.queryByText("research")).not.toBeInTheDocument();
  });
});
