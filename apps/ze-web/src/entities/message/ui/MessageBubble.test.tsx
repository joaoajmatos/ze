import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageBubble } from "./MessageBubble";
import { useTraceStore } from "@/features/trace-state";

const baseMessage = {
  id: "msg-1",
  role: "assistant" as const,
  text: "Hello there",
  components: [] as [],
  read: true,
  created_at: "2026-06-15T12:00:00.000Z",
  thread_id: "ze-thread",
};

describe("MessageBubble", () => {
  it("renders text and components in order", () => {
    render(
      <MessageBubble
        message={{
          ...baseMessage,
          components: [
            {
              type: "col",
              children: [
                { type: "text", content: "$2.00", style: "heading" },
                { type: "text", content: "Spend", style: "label" },
              ],
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Hello there")).toBeInTheDocument();
    expect(screen.getByText("$2.00")).toBeInTheDocument();
    expect(screen.getByText("Spend")).toBeInTheDocument();
  });

  it("shows a visible workspace chip when the turn used the workspace", () => {
    useTraceStore.setState({
      traces: [
        {
          type: "trace_update",
          message_id: "msg-1",
          agent: "companion",
          routing_method: "embedding",
          confidence: 0.9,
          score_gap: 0.1,
          is_compound: false,
          subtasks: [],
          memory_chunks: [],
          tool_calls: [],
          total_duration_ms: 10,
          skills_used: [],
          workspace: { mode: "ask", runs: [], files: [], script_ran: false, unavailable: false },
        } as never,
      ],
    });
    render(<MessageBubble message={baseMessage} />);
    expect(screen.getByTestId("workspace-chip")).toHaveTextContent("Workspace · ask");
    useTraceStore.setState({ traces: [] });
  });
});
