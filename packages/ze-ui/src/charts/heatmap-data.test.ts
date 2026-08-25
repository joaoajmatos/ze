import { describe, expect, it } from "vitest";
import { contributionLevel, pointsToHeatmapGrid } from "./heatmap-data";

describe("pointsToHeatmapGrid", () => {
  it("builds Monday-first week columns and maps empty days to level 0", () => {
    const grid = pointsToHeatmapGrid([
      { x: "2026-08-17", y: 4 },
      { x: "2026-08-19", y: 1 },
    ]);

    expect(grid.rows).toBe(7);
    expect(grid.columns).toBeGreaterThanOrEqual(1);
    const monday = grid.cells.find((cell) => cell.iso === "2026-08-17");
    const wednesday = grid.cells.find((cell) => cell.iso === "2026-08-19");
    const tuesday = grid.cells.find((cell) => cell.iso === "2026-08-18");
    expect(monday?.row).toBe(0);
    expect(wednesday?.row).toBe(2);
    expect(tuesday?.value).toBe(0);
    expect(tuesday?.level).toBe(0);
    expect(monday?.level).toBe(4);
    expect(wednesday?.level).toBe(1);
  });
});

describe("contributionLevel", () => {
  it("returns 0 for empty values", () => {
    expect(contributionLevel(0, 10)).toBe(0);
    expect(contributionLevel(5, 0)).toBe(0);
  });
});
