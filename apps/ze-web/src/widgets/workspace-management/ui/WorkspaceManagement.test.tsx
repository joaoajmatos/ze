import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceManagement } from "./WorkspaceManagement";

const {
  useWorkspaceQuery,
  useWorkspaceFilesQuery,
  useWorkspaceRunsQuery,
  useWorkspaceModeMutation,
  useWorkspaceUploadMutation,
  useWorkspaceResetMutation,
  useCancelWorkspaceRunMutation,
  retrieveWorkspaceFile,
} = vi.hoisted(() => ({
  useWorkspaceQuery: vi.fn(),
  useWorkspaceFilesQuery: vi.fn(),
  useWorkspaceRunsQuery: vi.fn(),
  useWorkspaceModeMutation: vi.fn(),
  useWorkspaceUploadMutation: vi.fn(),
  useWorkspaceResetMutation: vi.fn(),
  useCancelWorkspaceRunMutation: vi.fn(),
  retrieveWorkspaceFile: vi.fn(),
}));

vi.mock("@/entities/workspace", () => ({
  useWorkspaceQuery,
  useWorkspaceFilesQuery,
  useWorkspaceRunsQuery,
  useWorkspaceModeMutation,
  useWorkspaceUploadMutation,
  useWorkspaceResetMutation,
  useCancelWorkspaceRunMutation,
  retrieveWorkspaceFile,
}));

const files = [
  {
    path: "notes.txt",
    size: 12,
    modified_at: "2026-08-14T12:00:00.000Z",
    is_dir: false,
  },
];

function setup() {
  const modeMutate = vi.fn();
  const uploadMutate = vi.fn();
  const resetMutate = vi.fn();
  useWorkspaceQuery.mockReturnValue({
    data: {
      available: true,
      mode: "ask",
      bytes_used: 12,
      bytes_ceiling: 1073741824,
      busy: false,
      last_reset_at: null,
      last_used_at: null,
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
  useWorkspaceFilesQuery.mockReturnValue({
    data: files,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
  useWorkspaceRunsQuery.mockReturnValue({
    data: [
      {
        id: "run-1",
        command: "echo hi",
        origin: "conversation",
        status: "succeeded",
      },
    ],
    isLoading: false,
    isError: false,
  });
  useWorkspaceModeMutation.mockReturnValue({ mutate: modeMutate, isPending: false });
  useWorkspaceUploadMutation.mockReturnValue({ mutate: uploadMutate, isPending: false });
  useWorkspaceResetMutation.mockReturnValue({ mutate: resetMutate, isPending: false });
  useCancelWorkspaceRunMutation.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    variables: undefined,
  });
  return { modeMutate, uploadMutate, resetMutate };
}

describe("WorkspaceManagement", () => {
  it("lists file names, sizes, and mtimes", () => {
    setup();
    render(<WorkspaceManagement />);
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getAllByText(/12 B/).length).toBeGreaterThan(0);
    expect(screen.getByText("conversation")).toBeInTheDocument();
  });

  it("uploads a chosen file", () => {
    const { uploadMutate } = setup();
    const { container } = render(<WorkspaceManagement />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["hello"], "hello.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(uploadMutate).toHaveBeenCalledWith(file);
  });

  it("retrieves a file when Retrieve is clicked", async () => {
    setup();
    retrieveWorkspaceFile.mockResolvedValue(new Blob(["hello"]));
    const createObjectURL = vi.fn(() => "blob:test");
    const revoke = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: revoke });
    render(<WorkspaceManagement />);
    fireEvent.click(screen.getByText("Retrieve"));
    expect(retrieveWorkspaceFile).toHaveBeenCalledWith("notes.txt");
  });

  it("issues reset then requires confirm before wiping", () => {
    const { resetMutate } = setup();
    resetMutate.mockImplementation((_args: unknown, opts?: { onSuccess?: (d: { confirmation_id: string }) => void }) => {
      opts?.onSuccess?.({ confirmation_id: "c1" });
    });
    render(<WorkspaceManagement />);
    fireEvent.click(screen.getByText("Reset"));
    expect(resetMutate).toHaveBeenCalled();
    expect(screen.getByText(/Reset the workspace/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Confirm reset"));
    expect(resetMutate).toHaveBeenCalledWith(
      { confirmationId: "c1", choice: "approve" },
      expect.anything(),
    );
  });

  it("switches workspace mode", () => {
    const { modeMutate } = setup();
    render(<WorkspaceManagement />);
    fireEvent.change(screen.getByLabelText("Workspace mode"), { target: { value: "auto" } });
    expect(modeMutate).toHaveBeenCalledWith("auto");
  });
});
