import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceManagement } from "./WorkspaceManagement";

const { useWorkspaceQuery, useWorkspaceFilesQuery } = vi.hoisted(() => ({
  useWorkspaceQuery: vi.fn(),
  useWorkspaceFilesQuery: vi.fn(),
}));

vi.mock("@/entities/workspace", () => ({
  useWorkspaceQuery,
  useWorkspaceFilesQuery,
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
  useWorkspaceQuery.mockReturnValue({
    data: {
      available: true,
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
}

describe("WorkspaceManagement", () => {
  it("lists file names, sizes, and mtimes", () => {
    setup();
    render(<WorkspaceManagement />);
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getAllByText(/12 B/).length).toBeGreaterThan(0);
  });

  it("does not offer console controls", () => {
    setup();
    render(<WorkspaceManagement />);
    expect(screen.queryByText("Upload")).not.toBeInTheDocument();
    expect(screen.queryByText("Reset")).not.toBeInTheDocument();
    expect(screen.queryByText("Retrieve")).not.toBeInTheDocument();
    expect(screen.queryByText("Recent activity")).not.toBeInTheDocument();
  });
});
