import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { GraphToolbar } from "./GraphToolbar";

vi.mock("@myguyze/ze-ui/charts", () => ({
  PieChart: ({ data, title }: { data: { x: string; y: number }[]; title?: string }) => (
    <div data-testid={`pie-${title}`} data-empty={data.length === 0 ? "true" : "false"}>
      {data.map((point) => (
        <span key={point.x} data-point={`${point.x}:${point.y}`} />
      ))}
    </div>
  ),
}));

function showCharts() {
  fireEvent.click(screen.getByRole("button", { name: "Charts" }));
}

describe("GraphToolbar", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("keeps composition charts hidden until Charts is pressed", () => {
    render(
      <GraphToolbar
        entityType="all"
        onEntityTypeChange={vi.fn()}
        onFitView={vi.fn()}
        onResetLayout={vi.fn()}
        composition={{
          byEntityType: [{ x: "person", y: 2 }],
          byRelationType: [{ x: "knows", y: 1 }],
        }}
      />,
    );

    expect(screen.queryByTestId("pie-Entity types")).not.toBeInTheDocument();
    showCharts();
    expect(screen.getByTestId("pie-Entity types")).toBeInTheDocument();
  });

  it("renders composition charts matching loaded entity-type proportions", () => {
    render(
      <GraphToolbar
        entityType="all"
        onEntityTypeChange={vi.fn()}
        onFitView={vi.fn()}
        onResetLayout={vi.fn()}
        composition={{
          byEntityType: [
            { x: "person", y: 2 },
            { x: "topic", y: 1 },
          ],
          byRelationType: [{ x: "knows", y: 1 }],
        }}
      />,
    );
    showCharts();

    const entities = screen.getByTestId("pie-Entity types");
    expect(entities.querySelector("[data-point='person:2']")).toBeInTheDocument();
    expect(entities.querySelector("[data-point='topic:1']")).toBeInTheDocument();
    expect(screen.getByTestId("pie-Relation types").querySelector("[data-point='knows:1']")).toBeInTheDocument();
  });

  it("updates composition when neighbours are expanded", () => {
    const { rerender } = render(
      <GraphToolbar
        entityType="all"
        onEntityTypeChange={vi.fn()}
        onFitView={vi.fn()}
        onResetLayout={vi.fn()}
        composition={{
          byEntityType: [{ x: "person", y: 1 }],
          byRelationType: [],
        }}
      />,
    );
    showCharts();

    expect(screen.getByTestId("pie-Entity types").querySelector("[data-point='person:1']")).toBeInTheDocument();

    rerender(
      <GraphToolbar
        entityType="all"
        onEntityTypeChange={vi.fn()}
        onFitView={vi.fn()}
        onResetLayout={vi.fn()}
        composition={{
          byEntityType: [
            { x: "person", y: 1 },
            { x: "org", y: 2 },
          ],
          byRelationType: [{ x: "works_at", y: 2 }],
        }}
      />,
    );

    expect(screen.getByTestId("pie-Entity types").querySelector("[data-point='org:2']")).toBeInTheDocument();
  });

  it("hides empty composition pies even when Charts is on", () => {
    render(
      <GraphToolbar
        entityType="all"
        onEntityTypeChange={vi.fn()}
        onFitView={vi.fn()}
        onResetLayout={vi.fn()}
        composition={{ byEntityType: [], byRelationType: [] }}
      />,
    );
    showCharts();

    expect(screen.queryByTestId("pie-Entity types")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pie-Relation types")).not.toBeInTheDocument();
  });
});
