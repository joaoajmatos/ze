import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { WebCostSummaryResponse } from "@myguyze/ze-client";
import { CostsOverview } from "./CostsOverview";

const { useCostsQuery, useCostAnomaliesQuery } = vi.hoisted(() => ({
  useCostsQuery: vi.fn(),
  useCostAnomaliesQuery: vi.fn(),
}));

vi.mock("@/entities/cost-entry", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/entities/cost-entry")>();
  return { ...actual, useCostsQuery, useCostAnomaliesQuery };
});

vi.mock("@/widgets/activity-heatmap-panel", () => ({
  ActivityHeatmapPanel: () => <div data-testid="heatmap" />,
}));

vi.mock("@/features/open-context-overlay", () => ({
  FloatingButton: () => null,
}));

vi.mock("@myguyze/ze-ui/charts", () => ({
  HeatmapChart: ({ data, title }: { data: { x: string; y: number }[]; title?: string }) => (
    <div data-testid="spend-chart" data-title={title} data-count={data.length}>
      {data.map((point) => (
        <span key={point.x} data-point={`${point.x}:${point.y}`} />
      ))}
    </div>
  ),
  PieChart: ({ data, title }: { data: { x: string; y: number }[]; title?: string }) => (
    <div data-testid={`pie-${title}`} data-count={data.length}>
      {data.map((point) => (
        <span key={point.x} data-point={`${point.x}:${point.y}`} />
      ))}
    </div>
  ),
}));

const usage = {
  usd: 1,
  tokens: 100,
  calls: 2,
  prompt_tokens: 60,
  completion_tokens: 40,
};

function summary(overrides: Partial<WebCostSummaryResponse> = {}): WebCostSummaryResponse {
  return {
    total_usd: 2,
    total_tokens: 200,
    total_calls: 4,
    by_agent: { companion_agent: usage, research_agent: { ...usage, usd: 0.5 } },
    by_plugin: { ze_personal: usage, ze_news: { ...usage, usd: 0.4 }, other: { ...usage, usd: 0.1 } },
    by_day: [],
    period: "last 30 days",
    ...overrides,
  };
}

function setup(data: WebCostSummaryResponse) {
  useCostsQuery.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
  useCostAnomaliesQuery.mockReturnValue({
    data: { anomalies: [] },
    isLoading: false,
  });
}

describe("CostsOverview", () => {
  it("renders 30 zero-filled spend heatmap points including a day with usd 0", () => {
    const today = new Date().toISOString().slice(0, 10);
    setup(summary({ by_day: [{ date: today, usd: 1.25, calls: 2 }] }));

    render(<CostsOverview />);

    const chart = screen.getByTestId("spend-chart");
    expect(chart).toHaveAttribute("data-count", "30");
    expect(chart.querySelector(`[data-point='${today}:1.25']`)).toBeInTheDocument();
  });

  it("renders plugin and agent breakdown charts for multi-item and single-item data", () => {
    setup(summary());
    const { rerender } = render(<CostsOverview />);

    expect(screen.getByTestId("pie-Plugin share")).toHaveAttribute("data-count", "3");
    expect(screen.getByTestId("pie-Agent share")).toHaveAttribute("data-count", "2");
    expect(screen.getByText("Ze Personal")).toBeInTheDocument();
    expect(screen.getByText("Companion")).toBeInTheDocument();
    expect(screen.getByText(/calls/)).toBeInTheDocument();

    setup(
      summary({
        by_plugin: { ze_personal: usage },
        by_agent: { companion_agent: usage },
      }),
    );
    rerender(<CostsOverview />);

    expect(screen.getByTestId("pie-Plugin share")).toHaveAttribute("data-count", "1");
    expect(screen.getByTestId("pie-Agent share")).toHaveAttribute("data-count", "1");
  });
});
