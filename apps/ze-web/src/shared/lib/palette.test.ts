import { afterEach, describe, expect, it, vi } from "vitest";
import { applyPalette, readPalette, storePalette } from "./palette";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  delete document.documentElement.dataset.palette;
});

describe("palette", () => {
  it("defaults to orchid", () => {
    expect(readPalette()).toBe("orchid");
  });

  it("round-trips a stored palette", () => {
    storePalette("amethyst");
    expect(readPalette()).toBe("amethyst");
  });

  it("ignores an unknown stored value", () => {
    localStorage.setItem("ze.palette", "chartreuse");
    expect(readPalette()).toBe("orchid");
  });

  it("writes data-palette on the root", () => {
    applyPalette("ultraviolet");
    expect(document.documentElement.dataset.palette).toBe("ultraviolet");
  });

  it("survives storage that throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readPalette()).toBe("orchid");
    expect(() => storePalette("amethyst")).not.toThrow();
  });
});
