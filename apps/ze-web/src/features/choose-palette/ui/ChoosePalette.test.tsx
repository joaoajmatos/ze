import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChoosePalette } from "./ChoosePalette";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  delete document.documentElement.dataset.palette;
});

describe("ChoosePalette", () => {
  it("shows three palettes with Orchid pressed by default", () => {
    render(<ChoosePalette />);
    expect(screen.getByRole("button", { name: /Orchid/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Ultraviolet/ })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /Amethyst/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("applies and stores the choice, and survives a remount", () => {
    const { unmount } = render(<ChoosePalette />);
    fireEvent.click(screen.getByRole("button", { name: /Amethyst/ }));
    expect(document.documentElement.dataset.palette).toBe("amethyst");
    expect(localStorage.getItem("ze.palette")).toBe("amethyst");
    unmount();
    render(<ChoosePalette />);
    expect(screen.getByRole("button", { name: /Amethyst/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("falls back to Orchid and does not crash when storage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    render(<ChoosePalette />);
    expect(screen.getByRole("button", { name: /Orchid/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Ultraviolet/ }));
    expect(document.documentElement.dataset.palette).toBe("ultraviolet");
    expect(screen.getByRole("button", { name: /Ultraviolet/ })).toHaveAttribute("aria-pressed", "true");
  });
});
