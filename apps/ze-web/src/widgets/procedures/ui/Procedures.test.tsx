import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Procedures } from "./Procedures";

const { useProcedureCandidatesQuery, useProcedureLibraryQuery, useProcedureDetailQuery } = vi.hoisted(() => ({
  useProcedureCandidatesQuery: vi.fn(),
  useProcedureLibraryQuery: vi.fn(),
  useProcedureDetailQuery: vi.fn(),
}));

vi.mock("@/entities/procedure", () => ({ useProcedureCandidatesQuery, useProcedureLibraryQuery, useProcedureDetailQuery }));
vi.mock("@/features/review-procedure", () => ({ ReviewProcedureCandidate: () => <button type="button">Approve</button> }));
vi.mock("@/features/procedure-review", () => ({ ProcedureControls: () => <button type="button">Disable</button> }));

const candidate = { id: "c1", name: "Weekly review", source_kind: "goal", status: "pending", evidence_refs: [{ kind: "goal", id: "g1" }] };
const row = { id: "p1", name: "Inbox sweep", identity_status: "active", version_status: "active", version_number: 2, trigger: "clear the morning inbox", current_version_id: "v2", evidence_refs: [] };
const detail = {
  id: "p1",
  name: "Inbox sweep",
  identity_status: "active",
  versions: [{ id: "v2", version_number: 2, evidence_refs: [{ kind: "goal", id: "g1" }] }],
  events: [],
  outcomes: [{ outcome: "failed", summary: "send bounced", procedure_version_id: "v2" }],
};

describe("Procedures", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useProcedureCandidatesQuery.mockReturnValue({ data: [candidate], isLoading: false });
    useProcedureLibraryQuery.mockReturnValue({ data: [row], isLoading: false, isError: false, refetch: vi.fn() });
    useProcedureDetailQuery.mockImplementation((id?: string) => ({ data: id ? detail : undefined }));
  });

  it("puts candidates to review before the library", () => {
    render(<Procedures />);
    const candidates = screen.getByRole("group", { name: /waiting for your review/i });
    expect(within(candidates).getByText("Weekly review")).toBeInTheDocument();
    expect(within(candidates).getByRole("button", { name: "Approve" })).toBeInTheDocument();
    const library = screen.getByRole("group", { name: /what i know how to do/i });
    expect(candidates.compareDocumentPosition(library) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("describes status in words with version and opens detail with controls", () => {
    render(<Procedures />);
    expect(screen.getByText(/active · version 2/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /inbox sweep/i }));
    expect(screen.getByText("Disable")).toBeInTheDocument();
    expect(screen.getByText(/goal · g1/)).toBeInTheDocument();
    expect(screen.getByText("failed: send bounced")).toBeInTheDocument();
  });

  it("says when there is nothing yet", () => {
    useProcedureCandidatesQuery.mockReturnValue({ data: [], isLoading: false });
    useProcedureLibraryQuery.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
    render(<Procedures />);
    expect(screen.getByText(/no procedures yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /waiting for your review/i })).toBeNull();
  });

  it("shows an error with retry", () => {
    const refetch = vi.fn();
    useProcedureLibraryQuery.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch });
    render(<Procedures />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });
});
