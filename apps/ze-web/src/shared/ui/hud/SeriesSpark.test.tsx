import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeriesSpark, seriesPoints } from "./SeriesSpark";

describe("seriesPoints", () => {
  it("scales min to the bottom and max to the top", () => {
    const pts = seriesPoints([0, 5, 10], 100, 20);
    expect(pts[0]).toEqual([1, 19]);
    expect(pts[2]).toEqual([99, 1]);
    expect(pts[1][1]).toBeCloseTo(10);
  });

  it("returns nothing for empty input", () => {
    expect(seriesPoints([], 100, 20)).toEqual([]);
  });

  it("draws a single point at the baseline", () => {
    expect(seriesPoints([3], 100, 20)).toEqual([[50, 19]]);
  });

  it("draws an all-zero series flat at the baseline", () => {
    const pts = seriesPoints([0, 0, 0], 100, 20);
    expect(pts.every(([, y]) => y === 19)).toBe(true);
  });
});

describe("SeriesSpark", () => {
  it("keeps zero days on the baseline in a padded series", () => {
    const { container } = render(<SeriesSpark values={[0, 0, 4, 0]} label="Spend per day" />);
    const points = container.querySelector("polyline")!.getAttribute("points")!.split(" ");
    expect(points[0].split(",")[1]).toBe("19.0");
    expect(points[3].split(",")[1]).toBe("19.0");
  });

  it("labels the first, last and max values", () => {
    render(<SeriesSpark values={[1, 4, 2]} label="Spend per day" format={(n) => `$${n}`} />);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "Spend per day: first $1, last $2, max $4");
  });

  it("renders only a label for empty input", () => {
    const { container } = render(<SeriesSpark values={[]} label="Spend per day" />);
    expect(container.querySelector("polyline")).toBeNull();
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "Spend per day: no data");
  });
});
