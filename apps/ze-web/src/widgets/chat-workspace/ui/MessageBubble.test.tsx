import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageBubble } from "./MessageBubble";
import { useTraceStore } from "@/features/trace-state";

const { useWorkspaceRunEventsQuery } = vi.hoisted(() => ({
  useWorkspaceRunEventsQuery: vi.fn(),
}));

vi.mock("@/entities/workspace", () => ({ useWorkspaceRunEventsQuery }));
vi.mock("@/features/primitive-tree/api/useCardActions", () => ({
  useCardActions: () => vi.fn(),
}));

const baseMessage = {
  id: "msg-1",
  role: "assistant" as const,
  text: "Hello there",
  components: [] as [],
  read: true,
  created_at: "2026-06-15T12:00:00.000Z",
  thread_id: "ze-thread",
};

function seedWorkspaceTrace(workspace: Record<string, unknown> | null, sources?: unknown[]) {
  useTraceStore.setState({
    byThread: {
      "ze-thread": {
        traces: [
          {
            type: "trace_update",
            thread_id: "ze-thread",
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
            workspace,
            sources,
          } as never,
        ],
        pending: false,
        pendingTrace: null,
        hydrating: false,
      },
    },
  });
}

describe("MessageBubble", () => {
  beforeEach(() => {
    useTraceStore.setState({ byThread: {} });
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
    seedWorkspaceTrace({ runs: [], files: [], script_ran: false, unavailable: false });
    render(<MessageBubble message={baseMessage} />);
    expect(screen.getByTestId("workspace-chip")).toHaveTextContent("Workspace · used");
  });

  it("shows a still-running chip instead of the workspace chip when a run detached", () => {
    seedWorkspaceTrace({
      runs: [{ command: "sleep 60", status: "in_progress" }],
      files: [],
      script_ran: false,
      unavailable: false,
    });
    render(<MessageBubble message={baseMessage} />);
    expect(screen.getByTestId("workspace-still-running-chip")).toHaveTextContent(
      "Still running · sleep 60",
    );
    expect(screen.queryByTestId("workspace-chip")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workspace-live-output")).not.toBeInTheDocument();
  });

  it("shows growing live output under the chip when the run has an id", () => {
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "fetching 40 files...\n",
      lastSeq: 0,
      status: "streaming",
      exitCode: null,
      looksBinary: false,
    });
    seedWorkspaceTrace({
      runs: [{ id: "8f14e45f-ceea-4b19-9b8e-3f9b5c1e2a3d", command: "sleep 60", status: "in_progress" }],
      files: [],
      script_ran: false,
      unavailable: false,
    });
    render(<MessageBubble message={baseMessage} />);
    expect(useWorkspaceRunEventsQuery).toHaveBeenCalledWith(
      "8f14e45f-ceea-4b19-9b8e-3f9b5c1e2a3d",
    );
    expect(screen.getByTestId("workspace-live-output")).toHaveTextContent(
      "fetching 40 files...",
    );
  });

  it("renders a not-printable note instead of raw text when output looks binary", () => {
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "����",
      lastSeq: 0,
      status: "streaming",
      exitCode: null,
      looksBinary: true,
    });
    seedWorkspaceTrace({
      runs: [{ id: "run-1", command: "cat image.png", status: "in_progress" }],
      files: [],
      script_ran: false,
      unavailable: false,
    });
    render(<MessageBubble message={baseMessage} />);
    expect(screen.queryByTestId("workspace-live-output")).not.toBeInTheDocument();
    expect(screen.getByText(/not printable/i)).toBeInTheDocument();
  });

  it("renders the actions slot for assistant replies only", () => {
    const { rerender } = render(
      <MessageBubble message={baseMessage} actions={<div data-testid="slot" />} />,
    );
    expect(screen.getByTestId("slot")).toBeInTheDocument();
    rerender(
      <MessageBubble
        message={{ ...baseMessage, role: "user" }}
        actions={<div data-testid="slot" />}
      />,
    );
    expect(screen.queryByTestId("slot")).not.toBeInTheDocument();
  });

  it("lists sources under the reply as safe external links", () => {
    seedWorkspaceTrace(null, [
      { url: "https://www.example.com/a", title: "Article A" },
      { url: "https://news.org/b", title: "" },
    ]);
    render(<MessageBubble message={baseMessage} />);
    const link = screen.getByRole("link", { name: "Article A" });
    expect(link).toHaveAttribute("href", "https://www.example.com/a");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "news.org" })).toHaveAttribute("href", "https://news.org/b");
  });

  it("renders no sources section when sources are empty or absent", () => {
    seedWorkspaceTrace(null, []);
    const { unmount } = render(<MessageBubble message={baseMessage} />);
    expect(screen.queryByTestId("message-sources")).not.toBeInTheDocument();
    unmount();
    seedWorkspaceTrace(null);
    render(<MessageBubble message={baseMessage} />);
    expect(screen.queryByTestId("message-sources")).not.toBeInTheDocument();
  });

  it("does not show sources on user messages", () => {
    seedWorkspaceTrace(null, [{ url: "https://a.com", title: "A" }]);
    render(<MessageBubble message={{ ...baseMessage, role: "user" }} />);
    expect(screen.queryByTestId("message-sources")).not.toBeInTheDocument();
  });
});
