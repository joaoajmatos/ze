import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { WorkspaceRunItem } from "@/entities/workspace";
import { RunningRunBanner } from "./RunningRunBanner";

const { useCancelWorkspaceRunMutation } = vi.hoisted(() => ({
  useCancelWorkspaceRunMutation: vi.fn(),
}));

vi.mock("@/entities/workspace", async () => {
  const actual = await vi.importActual<object>("@/entities/workspace");
  return { ...actual, useCancelWorkspaceRunMutation };
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
});
