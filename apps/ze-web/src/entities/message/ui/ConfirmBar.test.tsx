import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmBar } from "./ConfirmBar";

const actions = [
  { label: "Approve", value: "approve", style: "primary" as const },
  { label: "Cancel", value: "deny", style: "secondary" as const },
];

describe("ConfirmBar", () => {
  it("shows an edit field when editable and sends edited content on approve", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmBar
        prompt="Write report.md in workspace mode ask?"
        actions={actions}
        onConfirm={onConfirm}
        editable
        proposed="draft"
      />,
    );

    expect(screen.getByText(/workspace mode ask/i)).toBeInTheDocument();
    const field = screen.getByLabelText("Edit proposed workspace content");
    fireEvent.change(field, { target: { value: "edited" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onConfirm).toHaveBeenCalledWith("approve", "edited");
  });

  it("hides the edit field when not editable", () => {
    render(
      <ConfirmBar prompt="Reset workspace?" actions={actions} onConfirm={() => undefined} />,
    );
    expect(screen.queryByLabelText("Edit proposed workspace content")).not.toBeInTheDocument();
  });
});
