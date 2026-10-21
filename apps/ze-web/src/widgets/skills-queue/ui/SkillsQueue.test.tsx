import type { SkillResponse } from "@myguyze/ze-client";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const transition = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false }));
const imp = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false }));
vi.mock("@/entities/skill", () => ({ useSkillTransitionMutation: () => transition, useSkillImportMutation: () => imp }));

import { SkillsQueue } from "./SkillsQueue";

const skill = (o: Partial<SkillResponse> & Record<string, unknown>): SkillResponse =>
  ({ id: "s1", name: "Summarise", description: "Summarises things", status: "active", source: "bundled", ...o }) as SkillResponse;
const base = { loading: false, error: false };

describe("SkillsQueue", () => {
  beforeEach(() => {
    transition.mutate.mockReset();
    imp.mutate.mockReset();
    imp.isError = false;
  });

  it("lists pending review first with approve and reject", () => {
    render(<SkillsQueue {...base} skills={[skill({ id: "a", name: "Active one" }), skill({ id: "p", name: "Pending one", status: "pending_review" })]} />);
    const groups = screen.getAllByRole("list");
    expect(within(groups[0]).getByText("Pending one")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(transition.mutate).toHaveBeenCalledWith({ skillId: "p", kind: "approve" });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(transition.mutate).toHaveBeenCalledWith({ skillId: "p", kind: "reject" });
  });

  it("turns installed skills on and off, and removes imported ones", () => {
    render(<SkillsQueue {...base} skills={[skill({ id: "a", source: "imported" }), skill({ id: "d", name: "Off one", status: "disabled" })]} />);
    fireEvent.click(screen.getByRole("button", { name: "Turn off" }));
    expect(transition.mutate).toHaveBeenCalledWith({ skillId: "a", kind: "disable" });
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(transition.mutate).toHaveBeenCalledWith({ skillId: "a", kind: "remove" });
    fireEvent.click(screen.getByRole("button", { name: "Turn on" }));
    expect(transition.mutate).toHaveBeenCalledWith({ skillId: "d", kind: "enable" });
  });

  it("keeps executable approval a separate step", () => {
    render(<SkillsQueue {...base} skills={[skill({ has_scripts: true, executable_approved: false, script_filenames: ["run.sh"] })]} />);
    expect(screen.getByText(/Contains scripts: run.sh/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve executables" }));
    expect(transition.mutate).toHaveBeenCalledWith({ skillId: "s1", kind: "approve-executables" });
  });

  it("imports by link and shows the error line on failure", () => {
    const { rerender } = render(<SkillsQueue {...base} skills={[]} />);
    fireEvent.change(screen.getByLabelText("Add a skill from a link"), { target: { value: " https://x.dev/SKILL.md " } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(imp.mutate).toHaveBeenCalledWith({ url: "https://x.dev/SKILL.md" }, expect.anything());
    imp.isError = true;
    rerender(<SkillsQueue {...base} skills={[]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't import");
  });

  it("no empty line while loading or on error", () => {
    const { rerender } = render(<SkillsQueue {...base} loading skills={[]} />);
    expect(screen.queryByText(/No skills installed/)).toBeNull();
    rerender(<SkillsQueue {...base} error skills={[]} />);
    expect(screen.getByText("Couldn't read your skills.")).toBeInTheDocument();
  });

  it("uses words for status", () => {
    const { container } = render(<SkillsQueue {...base} skills={[skill({ status: "pending_review" })]} />);
    expect(container.textContent).not.toMatch(/pending_review/);
  });
  it("Chat about this on a skill row passes a skill ref", () => {
    const onChatAbout = vi.fn();
    render(<SkillsQueue {...base} skills={[skill({})]} onChatAbout={onChatAbout} />);
    fireEvent.click(screen.getByRole("button", { name: "Chat about Summarise" }));
    expect(onChatAbout).toHaveBeenCalledWith(expect.objectContaining({ kind: "skill", id: "s1", label: expect.any(String) }), expect.anything());
  });
});
