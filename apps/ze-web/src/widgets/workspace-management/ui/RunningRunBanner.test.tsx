import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkspaceRunItem } from "@/entities/workspace";
import { RunningRunBanner } from "./RunningRunBanner";

const { useCancelWorkspaceRunMutation, useWorkspaceRunEventsQuery } = vi.hoisted(() => ({
  useCancelWorkspaceRunMutation: vi.fn(),
  useWorkspaceRunEventsQuery: vi.fn(),
}));

vi.mock("@/entities/workspace", async () => {
  const actual = await vi.importActual<object>("@/entities/workspace");
  return { ...actual, useCancelWorkspaceRunMutation, useWorkspaceRunEventsQuery };
});

function run(overrides: Partial<WorkspaceRunItem> = {}): WorkspaceRunItem {
  return {
    id: "run-1",
    started_at: "2026-08-15T12:00:00.000Z",
    ended_at: null,
    command: "sleep 60",
    origin: "conversation",
    thread_id: "t1",
    message_id: null,
    skill_id: null,
    skill_script_path: null,
    status: "in_progress",
    exit_code: null,
    output_preview: "",
    output_file_path: null,
    files_touched: [],
    error_summary: null,
    follow_through_notified: false,
    ...overrides,
  };
}

function mockMutation(overrides: Record<string, unknown> = {}) {
  const mutate = vi.fn();
  useCancelWorkspaceRunMutation.mockReturnValue({
    mutate,
    isPending: false,
    isError: false,
    error: null,
    variables: undefined,
    ...overrides,
  });
  return mutate;
}

describe("RunningRunBanner", () => {
  beforeEach(() => {
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "",
      lastSeq: null,
      status: "streaming",
      exitCode: null,
      looksBinary: false,
    });
  });

  it("renders nothing when there is no in-progress run", () => {
    mockMutation();
    const { container } = render(
      <RunningRunBanner runs={[run({ ended_at: "2026-08-15T12:01:00.000Z", status: "succeeded" })]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows the command for an in-progress run", () => {
    mockMutation();
    render(<RunningRunBanner runs={[run()]} />);
    expect(screen.getByTestId("running-run-banner")).toBeInTheDocument();
    expect(screen.getByText(/sleep 60/)).toBeInTheDocument();
    expect(screen.getByText(/still running/)).toBeInTheDocument();
  });

  it("ignores runs that already finished", () => {
    mockMutation();
    render(
      <RunningRunBanner
        runs={[run({ id: "a", ended_at: "2026-08-15T12:01:00.000Z", status: "succeeded" }), run({ id: "b" })]}
      />,
    );
    expect(screen.getAllByText(/sleep 60/)).toHaveLength(1);
  });

  it("cancels the run when the Stop button is clicked", () => {
    const mutate = mockMutation();
    render(<RunningRunBanner runs={[run({ id: "run-42" })]} />);

    fireEvent.click(screen.getByTestId("cancel-run-button"));

    expect(mutate).toHaveBeenCalledWith("run-42");
  });

  it("shows a stopping state while the cancel mutation is pending", () => {
    mockMutation({ isPending: true, variables: "run-1" });
    render(<RunningRunBanner runs={[run()]} />);

    const button = screen.getByTestId("cancel-run-button");
    expect(button).toHaveTextContent(/stopping/i);
    expect(button).toBeDisabled();
  });

  it("shows an already-finished error when the cancel mutation gets a 409", async () => {
    const { ApiError } = await import("@myguyze/ze-client");
    mockMutation({ isError: true, error: new ApiError(409, "already finished"), variables: "run-1" });
    render(<RunningRunBanner runs={[run()]} />);

    expect(screen.getByTestId("cancel-run-error")).toHaveTextContent(/already finished/i);
  });

  it("shows growing live output for an in-progress run", () => {
    mockMutation();
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "fetching 40 files...\n",
      lastSeq: 0,
      status: "streaming",
      exitCode: null,
      looksBinary: false,
    });
    render(<RunningRunBanner runs={[run({ id: "run-1" })]} />);

    expect(useWorkspaceRunEventsQuery).toHaveBeenCalledWith("run-1");
    expect(screen.getByTestId("workspace-run-live-output")).toHaveTextContent(
      "fetching 40 files...",
    );
  });

  it("shows a not-printable note instead of raw text when output looks binary", () => {
    mockMutation();
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "����",
      lastSeq: 0,
      status: "streaming",
      exitCode: null,
      looksBinary: true,
    });
    render(<RunningRunBanner runs={[run({ id: "run-1" })]} />);

    expect(screen.queryByTestId("workspace-run-live-output")).not.toBeInTheDocument();
    expect(screen.getByText(/not printable/i)).toBeInTheDocument();
  });

  it("stops showing new output once the run is cancelled and disappears from in-progress", () => {
    mockMutation();
    useWorkspaceRunEventsQuery.mockReturnValue({
      lines: "still going...\n",
      lastSeq: 0,
      status: "streaming",
      exitCode: null,
      looksBinary: false,
    });
    const { rerender } = render(<RunningRunBanner runs={[run({ id: "run-1" })]} />);
    expect(screen.getByTestId("workspace-run-live-output")).toBeInTheDocument();

    // Cancel succeeds -> refetch removes the row from in-progress (ended_at set).
    rerender(
      <RunningRunBanner
        runs={[
          run({
            id: "run-1",
            ended_at: "2026-08-15T12:05:00.000Z",
            status: "cancelled",
          }),
        ]}
      />,
    );
    expect(screen.queryByTestId("workspace-run-live-output")).not.toBeInTheDocument();
  });
});
