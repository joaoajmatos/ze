import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BrainMemoryPage } from "./BrainMemoryPage";

const { useMemoryActivityQuery, useMemoryTimelineBoundsQuery } = vi.hoisted(() => ({
  useMemoryActivityQuery: vi.fn(),
  useMemoryTimelineBoundsQuery: vi.fn(),
}));

vi.mock("@/entities/memory-feed-item", () => ({
  useMemoryActivityQuery,
  useMemoryTimelineBoundsQuery,
}));

vi.mock("@/widgets/memory-feed", () => ({
  MemoryFeed: () => <div data-testid="memory-feed" />,
}));

vi.mock("@/widgets/timeline-scrubber", () => ({
  TimelineScrubber: ({ onChange }: { onChange: (value: Date | null) => void }) => (
    <button type="button" onClick={() => onChange(new Date("2026-06-01T12:00:00Z"))}>
      scrub
    </button>
  ),
}));

function setupActivity(
  days: { date: string; count: number; fact_count: number; episode_count: number }[],
) {
  useMemoryTimelineBoundsQuery.mockReturnValue({
    data: { earliest: "2026-01-01T00:00:00Z", latest: "2026-08-19T00:00:00Z" },
  });
  useMemoryActivityQuery.mockReturnValue({
    data: { days, max_count: Math.max(0, ...days.map((d) => d.count)) },
  });
}

describe("BrainMemoryPage", () => {
  it("passes asOfDate as the activity query end when scrubbed to a past date", () => {
    setupActivity([]);
    render(<BrainMemoryPage />);

    fireEvent.click(screen.getByText("scrub"));

    const lastCall = useMemoryActivityQuery.mock.calls.at(-1) as [Date | undefined, Date | undefined];
    expect(lastCall[1]?.toISOString()).toBe("2026-06-01T12:00:00.000Z");
  });

  it("does not render growth or composition charts", () => {
    setupActivity([{ date: "2026-07-01", count: 5, fact_count: 3, episode_count: 2 }]);
    render(<BrainMemoryPage />);

    expect(screen.queryByRole("button", { name: "Charts" })).not.toBeInTheDocument();
    expect(screen.getByTestId("memory-feed")).toBeInTheDocument();
  });
});
