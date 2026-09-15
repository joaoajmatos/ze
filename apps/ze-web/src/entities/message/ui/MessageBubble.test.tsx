import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageBubble } from "./MessageBubble";
import { useTraceStore } from "@/features/trace-state";

const { useWorkspaceRunEventsQuery } = vi.hoisted(() => ({
  useWorkspaceRunEventsQuery: vi.fn(),
}));

vi.mock("@/entities/workspace", () => ({ useWorkspaceRunEventsQuery }));

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
  beforeEach(() => {
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "",
      lastSeq: null,
      status: "streaming",
      exitCode: null,
      looksBinary: false,
    });
  });

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

  it("shows a still-running chip instead of the workspace chip when a run detached", () => {
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
          workspace: {
            mode: "auto",
            runs: [{ command: "sleep 60", status: "in_progress" }],
            files: [],
            script_ran: false,
            unavailable: false,
          },
        } as never,
      ],
    });
    render(<MessageBubble message={baseMessage} />);
    expect(screen.getByTestId("workspace-still-running-chip")).toHaveTextContent(
      "Still running · sleep 60",
    );
    expect(screen.queryByTestId("workspace-chip")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workspace-live-output")).not.toBeInTheDocument();
    useTraceStore.setState({ traces: [] });
  });

  it("shows growing live output under the chip when the run has an id", () => {
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "fetching 40 files...\n",
      lastSeq: 0,
      status: "streaming",
      exitCode: null,
      looksBinary: false,
    });
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
          workspace: {
            mode: "auto",
            runs: [{ id: "8f14e45f-ceea-4b19-9b8e-3f9b5c1e2a3d", command: "sleep 60", status: "in_progress" }],
            files: [],
            script_ran: false,
            unavailable: false,
          },
        } as never,
      ],
    });
    render(<MessageBubble message={baseMessage} />);
    expect(useWorkspaceRunEventsQuery).toHaveBeenCalledWith(
      "8f14e45f-ceea-4b19-9b8e-3f9b5c1e2a3d",
    );
    expect(screen.getByTestId("workspace-live-output")).toHaveTextContent(
      "fetching 40 files...",
    );
    useTraceStore.setState({ traces: [] });
  });

  it("renders a not-printable note instead of raw text when output looks binary", () => {
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "����",
      lastSeq: 0,
      status: "streaming",
      exitCode: null,
      looksBinary: true,
    });
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
          workspace: {
            mode: "auto",
            runs: [{ id: "run-1", command: "cat image.png", status: "in_progress" }],
            files: [],
            script_ran: false,
            unavailable: false,
          },
        } as never,
      ],
    });
    render(<MessageBubble message={baseMessage} />);
    expect(screen.queryByTestId("workspace-live-output")).not.toBeInTheDocument();
    expect(screen.getByText(/not printable/i)).toBeInTheDocument();
    useTraceStore.setState({ traces: [] });
  });
});
