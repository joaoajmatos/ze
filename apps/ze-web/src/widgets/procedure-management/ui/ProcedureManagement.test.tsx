import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProcedureManagement } from "./ProcedureManagement";

const { useProcedureLibraryQuery, useProcedureDetailQuery } = vi.hoisted(() => ({
  useProcedureLibraryQuery: vi.fn(),
  useProcedureDetailQuery: vi.fn(),
}));

vi.mock("@/entities/procedure", () => ({
  useProcedureLibraryQuery,
  useProcedureDetailQuery,
}));

vi.mock("@/features/procedure-review", () => ({
  ProcedureControls: () => <button type="button">Disable</button>,
}));

const summary = {
  id: "proc-1",
  name: "Inbox sweep",
  identity_status: "active",
  version_status: "active",
  version_number: 2,
  trigger: "clear the morning inbox",
  current_version_id: "ver-2",
  evidence_refs: [{ kind: "goal", id: "goal-1" }],
};

const detail = {
  id: "proc-1",
  name: "Inbox sweep",
  identity_status: "active",
  current_version_id: "ver-2",
  versions: [
    {
      id: "ver-2",
      procedure_id: "proc-1",
      version_number: 2,
      name: "Inbox sweep",
      trigger: "clear the morning inbox",
      preconditions: [],
      steps: ["open inbox"],
      success_criteria: ["done"],
      limits: [],
      provenance: "prompt_supplied",
      status: "active",
      evidence_refs: [{ kind: "goal", id: "goal-1" }],
      learning_refs: [],
    },
  ],
  events: [{ kind: "admitted", reason: "ok", version_id: "ver-2" }],
  outcomes: [{ outcome: "failed", summary: "send bounced", procedure_version_id: "ver-2" }],
};

describe("ProcedureManagement", () => {
  it("lists status, trigger, and opens evidence", () => {
    useProcedureLibraryQuery.mockReturnValue({
      data: [summary],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useProcedureDetailQuery.mockImplementation((procedureId?: string) => ({
      data: procedureId ? detail : undefined,
    }));
    render(<ProcedureManagement />);
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("clear the morning inbox")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Inbox sweep/ }));
    expect(screen.getByText(/goal · goal-1/)).toBeInTheDocument();
    expect(screen.getByText("failed: send bounced")).toBeInTheDocument();
    expect(screen.getByText("Disable")).toBeInTheDocument();
  });
});
