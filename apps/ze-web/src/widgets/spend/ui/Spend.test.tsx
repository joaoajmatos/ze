import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Spend } from "./Spend";

const { useCostsQuery, useCostAnomaliesQuery } = vi.hoisted(() => ({
  useCostsQuery: vi.fn(),
  useCostAnomaliesQuery: vi.fn(),
}));

vi.mock("@/entities/cost-entry", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/cost-entry")>()),
  useCostsQuery,
  useCostAnomaliesQuery,
}));

const bucket = (usd: number) => ({ usd, tokens: 10, calls: 1, prompt_tokens: 5, completion_tokens: 5 });

function setup(anomalies: unknown[] = []) {
  useCostsQuery.mockReturnValue({
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    data: {
      total_usd: 21,
      total_tokens: 100,
      total_calls: 9,
      period: "30d",
      by_agent: {
        research_agent: bucket(9),
        companion_agent: bucket(6),
        calendar_agent: bucket(3),
        email_agent: bucket(1.5),
        news_agent: bucket(1),
        finance_agent: bucket(0.4),
        goals_agent: bucket(0.1),
      },
      by_plugin: {},
      // 7 recent days at $7 total and one older day at $14: sparse on purpose.
      by_day: [
        { date: "2026-10-31", usd: 7, calls: 1 },
        { date: "2026-10-10", usd: 14, calls: 1 },
      ],
    },
  });
  useCostAnomaliesQuery.mockReturnValue({ isLoading: false, isError: false, refetch: vi.fn(), data: { anomalies, period_days: 30 } });
  render(<Spend />);
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-31T12:00:00Z"));
});
afterEach(() => vi.useRealTimers());

describe("Spend", () => {
  it("is labelled by its question", () => {
    setup();
    expect(screen.getByRole("heading", { name: "Am I spending normally?" })).toBeInTheDocument();
  });

  it("compares the 7-day and 30-day daily averages over calendar days", () => {
    setup();
    expect(document.querySelector(".sentence")).toHaveTextContent(/last 7 days \$1\.00\/day vs 30-day \$0\.95\/day/i);
  });

  it("shows no alert state when there are no anomalies", () => {
    setup();
    const count = screen.getByTestId("anomaly-count");
    expect(count).toHaveTextContent("0");
    expect(count).not.toHaveClass("hot");
  });

  it("colours the anomaly count coral and lists run against baseline", () => {
    setup([{ agent: "research_agent", run_cost_usd: 0.4321, baseline_cost_usd: 0.05, multiplier: 8.6, session_id: null, detected_at: new Date().toISOString() }]);
    expect(screen.getByTestId("anomaly-count")).toHaveClass("hot");
    expect(screen.getByText(/\$0\.4321 vs \$0\.0500/)).toBeInTheDocument();
    expect(screen.getByText(/8\.6×/)).toBeInTheDocument();
  });

  it("lists the top 5 flows with plain names and folds the rest into others", () => {
    setup();
    const list = screen.getByRole("list", { name: "Spend by flow, last 30 days" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(6);
    expect(items[0]).toHaveTextContent("Research");
    expect(items[0]).toHaveTextContent("$9.00");
    expect(items[5]).toHaveTextContent("Others");
    expect(items[5]).toHaveTextContent("$0.50");
  });

  it("draws one series over the padded 30 days", () => {
    setup();
    expect(screen.getByRole("img", { name: /spend per day/i })).toBeInTheDocument();
  });

  it("does not say zero unusual runs when the anomaly query fails or is loading", () => {
    useCostsQuery.mockReturnValue({ isLoading: false, isError: false, refetch: vi.fn(), data: { total_usd: 1, total_tokens: 1, total_calls: 1, period: "30d", by_agent: {}, by_plugin: {}, by_day: [] } });
    useCostAnomaliesQuery.mockReturnValue({ isLoading: false, isError: true, refetch: vi.fn(), data: undefined });
    const { unmount } = render(<Spend />);
    expect(screen.getByText(/could not load unusual runs/i)).toBeInTheDocument();
    expect(screen.queryByTestId("anomaly-count")).toBeNull();
    unmount();
    useCostAnomaliesQuery.mockReturnValue({ isLoading: true, isError: false, refetch: vi.fn(), data: undefined });
    render(<Spend />);
    expect(screen.getByText(/checking for unusual runs/i)).toBeInTheDocument();
    expect(screen.queryByTestId("anomaly-count")).toBeNull();
  });

  it("names a failed read in the module", () => {
    useCostsQuery.mockReturnValue({ isLoading: false, isError: true, refetch: vi.fn(), data: undefined });
    useCostAnomaliesQuery.mockReturnValue({ isLoading: false, isError: false, refetch: vi.fn(), data: undefined });
    render(<Spend />);
    expect(screen.getByText(/could not load spend/i)).toBeInTheDocument();
  });
});
