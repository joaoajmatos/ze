import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EntityDetailResponse, GraphEntityNode } from "@myguyze/ze-client";
import { EntityDetailPanel } from "./EntityDetailPanel";

vi.mock("@myguyze/ze-ui/charts", () => ({
  LineChart: ({
    data,
    title,
  }: {
    data: { x: string; y: number; series?: string }[];
    title?: string;
  }) => (
    <div data-testid="activity-chart" data-title={title}>
      {data.map((point) => (
        <span key={`${point.series}-${point.x}`} data-point={`${point.series}:${point.x}:${point.y}`} />
      ))}
    </div>
  ),
}));

const entity: GraphEntityNode = {
  id: "e1",
  entity_type: "person",
  canonical_name: "Ada",
  aliases: [],
  attrs: {},
  degree: 1,
};

function detail(overrides: Partial<EntityDetailResponse> = {}): EntityDetailResponse {
  return {
    entity,
    facts: [],
    episodes: [],
    neighbours: [],
    neighbour_edges: [],
    ...overrides,
  };
}

describe("EntityDetailPanel", () => {
  it("renders an activity chart for a multi-point entity", () => {
    render(
      <EntityDetailPanel
        entity={entity}
        isLoading={false}
        onClose={vi.fn()}
        onExpand={vi.fn()}
        detail={detail({
          facts: [
            {
              id: "f1",
              key: "color",
              value: "teal",
              agent: "companion",
              created_at: "2026-07-02T14:03:00Z",
            },
            {
              id: "f2",
              key: "city",
              value: "Lisbon",
              agent: "companion",
              created_at: "2026-07-10T09:00:00Z",
            },
          ],
          episodes: [
            {
              id: "ep1",
              agent: "companion",
              summary: "Talked about color",
              created_at: "2026-07-02T15:00:00Z",
            },
          ],
        })}
      />,
    );

    const chart = screen.getByTestId("activity-chart");
    expect(chart).toHaveAttribute("data-title", "Activity");
    expect(chart.querySelectorAll("[data-point]")).toHaveLength(3);
    expect(screen.getByText("Facts (2)")).toBeInTheDocument();
  });

  it("renders a sensible activity chart for a single-point entity", () => {
    render(
      <EntityDetailPanel
        entity={entity}
        isLoading={false}
        onClose={vi.fn()}
        onExpand={vi.fn()}
        detail={detail({
          facts: [
            {
              id: "f1",
              key: "color",
              value: "teal",
              agent: "companion",
              created_at: "2026-07-02T14:03:00Z",
            },
          ],
        })}
      />,
    );

    const chart = screen.getByTestId("activity-chart");
    expect(chart.querySelectorAll("[data-point]")).toHaveLength(1);
    expect(chart.querySelector("[data-point='fact:2026-07-02:1']")).toBeInTheDocument();
  });
});
