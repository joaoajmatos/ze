import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SkillManagementList } from "./SkillManagementList";

const { useSkillsQuery, useSkillImportMutation, useSkillTransitionMutation } = vi.hoisted(
  () => ({
    useSkillsQuery: vi.fn(),
    useSkillImportMutation: vi.fn(),
    useSkillTransitionMutation: vi.fn(),
  }),
);

vi.mock("@/entities/skill", () => ({
  useSkillsQuery,
  useSkillImportMutation,
  useSkillTransitionMutation,
}));

const pendingSkill: {
  id: string;
  name: string;
  slug: string;
  description: string;
  source: string;
  origin_url: string;
  bundling_plugin: string | null;
  status: string;
  has_scripts: boolean;
  executable_approved?: boolean;
  script_filenames?: string[];
  created_at: string;
  approved_at: string | null;
  last_checked_at: string | null;
  last_check_error: string | null;
} = {
  id: "skill-1",
  name: "Pirate Speak",
  slug: "pirate-speak",
  description: 'Ends every response with "Arrr!"',
  source: "imported",
  origin_url: "http://example.com/SKILL.md",
  bundling_plugin: null,
  status: "pending_review",
  has_scripts: false,
  created_at: new Date().toISOString(),
  approved_at: null,
  last_checked_at: null,
  last_check_error: null,
};

const activeSkill = {
  ...pendingSkill,
  id: "skill-2",
  name: "Calendar Concise",
  status: "active",
};

const bundledSkill = {
  ...pendingSkill,
  id: "skill-3",
  name: "Core Persona",
  source: "bundled",
  bundling_plugin: "PersonalPlugin",
  status: "active",
};

function setup(
  skills: (typeof pendingSkill)[],
  transitionMutate = vi.fn(),
  importMutate = vi.fn(),
) {
  useSkillsQuery.mockReturnValue({
    data: skills,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
  useSkillTransitionMutation.mockReturnValue({ mutate: transitionMutate, isPending: false });
  useSkillImportMutation.mockReturnValue({ mutate: importMutate, isPending: false });
  return { transitionMutate, importMutate };
}

describe("SkillManagementList", () => {
  it("shows the empty state when there are no skills", () => {
    setup([]);
    render(<SkillManagementList />);
    expect(screen.getByText("No skills installed yet.")).toBeInTheDocument();
  });

  it("renders mixed-state skills with status and source badges", () => {
    setup([pendingSkill, activeSkill, bundledSkill]);
    render(<SkillManagementList />);

    expect(screen.getByText("Pending review")).toBeInTheDocument();
    expect(screen.getAllByText("Active")).toHaveLength(2);
    expect(screen.getByText("Pirate Speak")).toBeInTheDocument();
    expect(screen.getByText("Calendar Concise")).toBeInTheDocument();
    expect(screen.getByText("Core Persona")).toBeInTheDocument();
  });

  it("offers approve/reject only for pending skills", () => {
    setup([pendingSkill, activeSkill]);
    render(<SkillManagementList />);

    expect(screen.getAllByText("Approve")).toHaveLength(1);
    expect(screen.getAllByText("Reject")).toHaveLength(1);
    expect(screen.getAllByText("Disable")).toHaveLength(1);
  });

  it("does not offer Remove for bundled skills", () => {
    setup([bundledSkill]);
    render(<SkillManagementList />);

    expect(screen.queryByText("Remove")).not.toBeInTheDocument();
  });

  it("triggers approve transition on click", () => {
    const { transitionMutate } = setup([pendingSkill]);
    render(<SkillManagementList />);

    fireEvent.click(screen.getByText("Approve"));

    expect(transitionMutate).toHaveBeenCalledWith({ skillId: "skill-1", kind: "approve" });
  });

  it("triggers disable transition for active skills", () => {
    const { transitionMutate } = setup([activeSkill]);
    render(<SkillManagementList />);

    fireEvent.click(screen.getByText("Disable"));

    expect(transitionMutate).toHaveBeenCalledWith({ skillId: "skill-2", kind: "disable" });
  });

  it("shows a script warning and a distinct executable-approval action", () => {
    const scripted = {
      ...activeSkill,
      has_scripts: true,
      executable_approved: false,
      script_filenames: ["scripts/helper.py"],
    };
    const { transitionMutate } = setup([scripted]);
    render(<SkillManagementList />);

    expect(screen.getByText(/Contains scripts/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Approve executables"));
    expect(transitionMutate).toHaveBeenCalledWith({
      skillId: "skill-2",
      kind: "approve-executables",
    });
  });

  it("submits the import form with the entered URL", () => {
    const { importMutate } = setup([]);
    render(<SkillManagementList />);

    fireEvent.change(screen.getByPlaceholderText("https://example.com/SKILL.md"), {
      target: { value: "http://example.com/SKILL.md" },
    });
    fireEvent.click(screen.getByText("Import"));

    expect(importMutate).toHaveBeenCalledWith(
      { url: "http://example.com/SKILL.md" },
      expect.anything(),
    );
  });
});
