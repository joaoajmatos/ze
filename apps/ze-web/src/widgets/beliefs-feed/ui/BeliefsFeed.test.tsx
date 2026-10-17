import type { MemoryFeedItem } from "@myguyze/ze-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BeliefsFeed } from "./BeliefsFeed";

const { useMemoryFeedQuery, useMemoryTimelineBoundsQuery, useReviewFactMutation, mutate, fetchNextPage } = vi.hoisted(() => ({
  useMemoryFeedQuery: vi.fn(),
  useMemoryTimelineBoundsQuery: vi.fn(),
  useReviewFactMutation: vi.fn(),
  mutate: vi.fn(),
  fetchNextPage: vi.fn(),
}));

vi.mock("@/entities/memory-feed-item", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/memory-feed-item")>()),
  useMemoryFeedQuery,
  useMemoryTimelineBoundsQuery,
  useReviewFactMutation,
}));

const fact: MemoryFeedItem = {
  id: "f1",
  type: "fact",
  key: "works_at",
  value: "Acme",
  confidence: 0.8,
  reviewed: false,
  contradicted: false,
  provenance: "raw",
  claim_kind: "identity",
  summary: null,
  prompt_snippet: null,
  agent: "companion",
  created_at: "2026-10-14T08:00:00Z",
};
const episode: MemoryFeedItem = { ...fact, id: "e1", type: "episode", key: null, value: null, claim_kind: null, confidence: null, provenance: null, summary: "We planned the Lisbon trip", created_at: "2026-10-15T08:00:00Z" };

function feed(items: MemoryFeedItem[], over: Record<string, unknown> = {}) {
  useMemoryFeedQuery.mockReturnValue({
    data: { pages: [{ items, next_before: null, total_facts: 1, total_episodes: 1 }] },
    isLoading: false,
    isError: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage,
    refetch: vi.fn(),
    ...over,
  });
}

describe("BeliefsFeed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useReviewFactMutation.mockReturnValue({ mutate, isPending: false });
    useMemoryTimelineBoundsQuery.mockReturnValue({ data: { earliest: "2026-01-01T00:00:00Z", latest: "2026-10-17T00:00:00Z" } });
  });

  it("renders facts as belief sentences and episodes differently, with no raw key", () => {
    feed([fact, episode]);
    const { container } = render(<BeliefsFeed />);
    expect(screen.getByText("Works at Acme")).toBeInTheDocument();
    expect(screen.getByText("We planned the Lisbon trip")).toBeInTheDocument();
    expect(container.querySelectorAll(".row.episode")).toHaveLength(1);
    expect(container.textContent).not.toMatch(/works_at/);
  });

  it("reviews a fact with confirm, reject and edit", () => {
    feed([fact]);
    render(<BeliefsFeed />);
    fireEvent.click(screen.getByRole("button", { name: /keep this/i }));
    expect(mutate).toHaveBeenCalledWith({ actions: [{ id: "f1", action: "confirm" }] });
    fireEvent.click(screen.getByRole("button", { name: /drop this/i }));
    expect(mutate).toHaveBeenCalledWith({ actions: [{ id: "f1", action: "reject" }] });
    fireEvent.click(screen.getByRole("button", { name: /edit this/i }));
    fireEvent.change(screen.getByRole("textbox", { name: /new value/i }), { target: { value: "Globex" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(mutate).toHaveBeenCalledWith({ actions: [{ id: "f1", action: "edit", value: "Globex" }] });
  });

  it("pages by the cursor", () => {
    feed([fact], { hasNextPage: true });
    render(<BeliefsFeed />);
    fireEvent.click(screen.getByRole("button", { name: /earlier/i }));
    expect(fetchNextPage).toHaveBeenCalled();
  });

  it("time-travels with the as-of control and prints the date as a readout", () => {
    feed([fact]);
    render(<BeliefsFeed />);
    expect(screen.getByText(/showing now/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/as of/i), { target: { value: "2026-09-01" } });
    expect(useMemoryFeedQuery).toHaveBeenLastCalledWith({ type: "all" }, expect.stringContaining("2026-09-01"));
    expect(screen.getByText(/1 Sept 2026|1 Sep 2026/)).toBeInTheDocument();
    expect(screen.getByText(/kinds and confidence as of now/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^now$/i }));
    expect(useMemoryFeedQuery).toHaveBeenLastCalledWith({ type: "all" }, undefined);
  });

  it("explains an empty memory", () => {
    feed([]);
    render(<BeliefsFeed />);
    expect(screen.getByText("I have not learned anything yet. Tell me about yourself or connect Gmail.")).toBeInTheDocument();
  });

  it("shows loading and error states", () => {
    useMemoryFeedQuery.mockReturnValue({ isLoading: true, data: undefined });
    const { rerender } = render(<BeliefsFeed />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    useMemoryFeedQuery.mockReturnValue({ isLoading: false, isError: true, data: undefined, refetch: vi.fn() });
    rerender(<BeliefsFeed />);
    expect(screen.getByText(/could not load/i)).toBeInTheDocument();
  });
});
