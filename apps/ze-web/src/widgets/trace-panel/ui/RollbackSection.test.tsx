import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useSession } from "@/entities/session";
import { RollbackSection } from "./RollbackSection";

const entries = [
  { entry_id: "e1", tool: "set_reminder", effect_phrase: "set a reminder", outcome: "undone" as const },
  { entry_id: "e2", tool: "create_goal", effect_phrase: "created a goal", outcome: "failed" as const },
];

describe("RollbackSection", () => {
  beforeEach(() => useSession.getState().setHighlightMessage(null));

  it("renders nothing without rollback data or while live", () => {
    const { container, rerender } = render(<RollbackSection />);
    expect(container).toBeEmptyDOMElement();
    rerender(<RollbackSection rollback={{ replaces: "m0", entries }} live />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists each undone entry with its outcome on a regenerated reply", () => {
    render(<RollbackSection rollback={{ replaces: "m0", entries }} />);
    expect(screen.getByText("Rolled back before this reply")).toBeInTheDocument();
    expect(screen.getByText("set a reminder")).toBeInTheDocument();
    expect(screen.getByText("Undone")).toBeInTheDocument();
    expect(screen.getByText("Could not undo")).toBeInTheDocument();
  });

  it("links to the replaced reply", () => {
    render(<RollbackSection rollback={{ replaces: "m0", entries }} />);
    fireEvent.click(screen.getByRole("button", { name: /view replaced reply/i }));
    expect(useSession.getState().highlightMessageId).toBe("m0");
  });

  it("shows the stored record on a retried reply", () => {
    render(<RollbackSection record={{ state: "partial", entries, replaced_by: null }} />);
    expect(screen.getByText("Rollback during retry")).toBeInTheDocument();
    expect(screen.getByText("created a goal")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /view replaced reply/i })).not.toBeInTheDocument();
  });
});
