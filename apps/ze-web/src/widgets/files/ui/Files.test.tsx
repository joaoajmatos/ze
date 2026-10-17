import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Files } from "./Files";

const m = vi.hoisted(() => ({ useWorkspaceQuery: vi.fn(), useWorkspaceFilesQuery: vi.fn() }));
vi.mock("@/entities/workspace", () => m);

const ok = (data: unknown) => ({ data, isLoading: false, isError: false, refetch: vi.fn() });

describe("Files", () => {
  it("shows the status line and the tree rows, read-only", () => {
    m.useWorkspaceQuery.mockReturnValue(ok({ available: true, bytes_used: 2048, bytes_ceiling: 1048576, busy: true, last_reset_at: null, last_used_at: null }));
    m.useWorkspaceFilesQuery.mockReturnValue(ok([{ path: "notes/a.md", size: 1536, modified_at: "2026-10-01T10:00:00Z", is_dir: false }]));
    render(<MemoryRouter><Files /></MemoryRouter>);
    expect(screen.getByText(/2\.0 KB of 1\.0 MB/)).toBeInTheDocument();
    expect(screen.getByText(/busy/i)).toBeInTheDocument();
    expect(screen.getByText("notes/a.md")).toBeInTheDocument();
    expect(screen.getByText(/1\.5 KB/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    expect(document.querySelector('input[type="file"]')).toBeNull();
  });

  it("says the workspace is off when it is unavailable", () => {
    m.useWorkspaceQuery.mockReturnValue(ok({ available: false, bytes_used: 0, bytes_ceiling: 0, busy: false, last_reset_at: null, last_used_at: null }));
    m.useWorkspaceFilesQuery.mockReturnValue(ok([]));
    render(<MemoryRouter><Files /></MemoryRouter>);
    expect(screen.getByText("Workspace is off")).toBeInTheDocument();
  });

  it("says an available workspace is empty", () => {
    m.useWorkspaceQuery.mockReturnValue(ok({ available: true, bytes_used: 0, bytes_ceiling: 100, busy: false, last_reset_at: null, last_used_at: null }));
    m.useWorkspaceFilesQuery.mockReturnValue(ok([]));
    render(<MemoryRouter><Files /></MemoryRouter>);
    expect(screen.getByText(/no files yet/i)).toBeInTheDocument();
  });
});
