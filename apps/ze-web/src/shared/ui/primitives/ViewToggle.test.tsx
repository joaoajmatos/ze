import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ViewToggle } from "./ViewToggle";

describe("ViewToggle", () => {
  it("names both buttons and reflects the active mode", () => {
    render(<ViewToggle value="list" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Grid view" })).toHaveAttribute("aria-pressed", "false");
  });

  it("reports the chosen mode", () => {
    const onChange = vi.fn();
    render(<ViewToggle value="list" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Grid view" }));
    expect(onChange).toHaveBeenCalledWith("grid");
  });
});
