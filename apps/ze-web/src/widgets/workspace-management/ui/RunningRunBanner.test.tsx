import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WorkspaceRunItem } from "@/entities/workspace";
import { RunningRunBanner } from "./RunningRunBanner";

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

describe("RunningRunBanner", () => {
  it("renders nothing when there is no in-progress run", () => {
    const { container } = render(
      <RunningRunBanner runs={[run({ ended_at: "2026-08-15T12:01:00.000Z", status: "succeeded" })]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows the command for an in-progress run", () => {
    render(<RunningRunBanner runs={[run()]} />);
    expect(screen.getByTestId("running-run-banner")).toBeInTheDocument();
    expect(screen.getByText(/sleep 60/)).toBeInTheDocument();
    expect(screen.getByText(/still running/)).toBeInTheDocument();
  });

  it("ignores runs that already finished", () => {
    render(
      <RunningRunBanner
        runs={[run({ id: "a", ended_at: "2026-08-15T12:01:00.000Z", status: "succeeded" }), run({ id: "b" })]}
      />,
    );
    expect(screen.getAllByText(/sleep 60/)).toHaveLength(1);
  });
});
