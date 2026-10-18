import type { WorkspaceRunResponse, WorkspaceStatusResponse } from "@myguyze/ze-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const events = vi.hoisted(() => ({ state: { lines: "", lastSeq: null, status: "streaming", exitCode: null, looksBinary: false } as Record<string, unknown> }));
const cancel = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false }));
vi.mock("@/entities/workspace", async (orig) => ({
  ...(await orig<object>()),
  useWorkspaceRunEventsQuery: () => events.state,
  useCancelWorkspaceRunMutation: () => cancel,
}));

import { Runs } from "./Runs";

const run = (o: Partial<WorkspaceRunResponse> = {}): WorkspaceRunResponse =>
  ({ id: "r1", started_at: "2026-10-18T11:00:00Z", ended_at: null, command: "python build.py", origin: "conversation", thread_id: null,
    message_id: null, skill_id: null, skill_script_path: null, status: "succeeded", exit_code: 0, output_preview: "all good",
    output_file_path: null, files_touched: [], error_summary: null, ...o }) as WorkspaceRunResponse;
const ws = (o: Partial<WorkspaceStatusResponse> = {}) => ({ available: true, busy: false, bytes_used: 0, bytes_ceiling: 1, last_reset_at: null, last_used_at: null, ...o }) as WorkspaceStatusResponse;
const now = new Date("2026-10-18T12:00:00Z");
function view(props: Partial<React.ComponentProps<typeof Runs>>) {
  const client = new QueryClient();
  const spy = vi.spyOn(client, "invalidateQueries");
  const utils = render(
    <QueryClientProvider client={client}>
      <Runs runs={[run()]} loading={false} error={false} workspace={ws()} now={now} offline={false} {...props} />
    </QueryClientProvider>,
  );
  return { ...utils, spy };
}

describe("Runs", () => {
  beforeEach(() => {
    events.state = { lines: "", lastSeq: null, status: "streaming", exitCode: null, looksBinary: false };
    cancel.mutate.mockReset();
    cancel.isError = false;
  });

  it("shows command, origin and status in words, exit code and verbatim output", () => {
    view({});
    expect(screen.getByText("python build.py")).toBeInTheDocument();
    expect(screen.getByText("Finished")).toBeInTheDocument();
    expect(screen.getByText(/From a chat · .* · exit 0/)).toBeInTheDocument();
    expect(screen.getByText("all good").tagName).toBe("PRE");
  });

  it("says not started when started_at is null and shows error_summary in plain words", () => {
    view({ runs: [run({ id: null, started_at: null, status: "refused", exit_code: null, error_summary: "Another run holds the workspace." })] });
    expect(screen.getByText(/not started/)).toBeInTheDocument();
    expect(screen.getByText("Another run holds the workspace.")).toBeInTheDocument();
    expect(screen.queryByText(/exit/)).toBeNull();
  });

  it("streams the running row and Cancel calls the mutation; none when id is null", () => {
    events.state = { ...events.state, lines: "step 1\nstep 2" };
    const { unmount } = view({ runs: [run({ status: "in_progress", output_preview: "", exit_code: null })] });
    expect(screen.getByText(/step 2/).tagName).toBe("PRE");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(cancel.mutate).toHaveBeenCalledWith("r1", expect.anything());
    unmount();
    view({ runs: [run({ id: null, status: "in_progress", output_preview: "" })] });
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("says binary output when the stream looks binary", () => {
    events.state = { ...events.state, lines: "����", looksBinary: true };
    view({ runs: [run({ status: "in_progress", output_preview: "" })] });
    expect(screen.getByText("binary output")).toBeInTheDocument();
  });

  it("shows a plain line when cancel finds the run gone", async () => {
    cancel.mutate.mockImplementation((_id, opts) => opts.onSuccess({ outcome: "gone", line: "already finished" }));
    view({ runs: [run({ status: "in_progress" })] });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByText("This run already finished.")).toBeInTheDocument();
  });

  it("invalidates runs and workspace when the stream closes", async () => {
    events.state = { ...events.state, status: "closed" };
    const { spy } = view({ runs: [run({ status: "in_progress" })] });
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
  });

  it("shows busy", () => {
    view({ workspace: ws({ busy: true }) });
    expect(screen.getByText("busy · one run at a time")).toBeInTheDocument();
  });

  it("says Workspace is off only inside Runs", () => {
    view({ workspace: ws({ available: false }), runs: [] });
    expect(screen.getByRole("alert")).toHaveTextContent("Workspace is off.");
  });

  it("is coral only for an unattended failed or timed out run", () => {
    const { container, unmount } = view({ runs: [run({ origin: "unattended", status: "failed", exit_code: 1 })] });
    expect(container.querySelector("li.row.hot")).not.toBeNull();
    unmount();
    const a = view({ runs: [run({ origin: "conversation", status: "failed" }), run({ id: "r2", origin: "unattended", status: "cancelled" })] });
    expect(a.container.querySelector(".hot")).toBeNull();
  });

  it("no empty state while loading or on error", () => {
    const { unmount } = view({ runs: [], loading: true });
    expect(screen.queryByText(/No runs yet/)).toBeNull();
    unmount();
    view({ runs: [], error: true });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't read");
  });
  it("Chat about this on a run row passes a workspace_run ref", () => {
    const onChatAbout = vi.fn();
    view({ onChatAbout });
    fireEvent.click(screen.getByRole("button", { name: "Chat about python build.py" }));
    expect(onChatAbout).toHaveBeenCalledWith({ kind: "workspace_run", id: "r1" }, expect.anything());
  });
});
