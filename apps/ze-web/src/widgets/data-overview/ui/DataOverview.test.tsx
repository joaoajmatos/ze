import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DataDomainItem, DataDomainsResponse } from "@myguyze/ze-client";
import { DataOverview } from "./DataOverview";

const { useDataDomainsQuery } = vi.hoisted(() => ({
  useDataDomainsQuery: vi.fn(),
}));

vi.mock("@/entities/data-domain", () => ({
  useDataDomainsQuery,
}));

vi.mock("@/shared/lib", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/lib")>();
  return { ...actual, useTopBarQuickActions: () => undefined };
});

vi.mock("@myguyze/ze-ui/charts", () => ({
  PieChart: ({ data, title }: { data: { x: string; y: number }[]; title?: string }) => (
    <div data-testid="category-chart" data-title={title} data-count={data.length} data-empty={data.length === 0 ? "true" : "false"}>
      {data.map((point) => (
        <span key={point.x} data-point={`${point.x}:${point.y}`} />
      ))}
    </div>
  ),
}));

function domain(name: string, size_bytes: number, count = 1): DataDomainItem {
  return { name, importable: false, count, size_bytes };
}

function setup(data: DataDomainsResponse) {
  useDataDomainsQuery.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
}

describe("DataOverview", () => {
  it("renders the category chart for multi-category, single-category, and empty storage", () => {
    setup({
      domains: [
        domain("memory.facts", 4000),
        domain("memory.episodes", 1000),
        domain("news.articles", 2000),
        domain("finance.tx", 500),
      ],
      schema_revisions: [],
      total_records: 10,
      total_size_bytes: 7500,
    });
    const { rerender } = render(<DataOverview />);

    const multi = screen.getByTestId("category-chart");
    expect(multi.querySelector("[data-point]")).not.toBeNull();

    setup({
      domains: [domain("memory.facts", 1000)],
      schema_revisions: [],
      total_records: 1,
      total_size_bytes: 1000,
    });
    rerender(<DataOverview />);
    expect(screen.getByTestId("category-chart")).toHaveAttribute("data-count", "1");

    setup({
      domains: [domain("memory.facts", 0, 0)],
      schema_revisions: [],
      total_records: 0,
      total_size_bytes: 0,
    });
    rerender(<DataOverview />);
    expect(screen.getByTestId("category-chart")).toHaveAttribute("data-empty", "true");
  });

  it("lists domain sizes without a per-group bar chart", () => {
    setup({
      domains: [
        domain("memory.facts", 4000),
        domain("memory.episodes", 2000),
        domain("memory.events", 0, 0),
      ],
      schema_revisions: [],
      total_records: 3,
      total_size_bytes: 6000,
    });

    render(<DataOverview />);

    expect(screen.queryByTestId("domain-chart")).not.toBeInTheDocument();
    expect(screen.getByText("facts")).toBeInTheDocument();
    expect(screen.getByText("episodes")).toBeInTheDocument();
    expect(screen.getByText("events")).toBeInTheDocument();
  });
});
