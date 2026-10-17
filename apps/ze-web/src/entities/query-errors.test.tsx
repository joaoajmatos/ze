import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { useContactsPageQuery } from "./contact";
import { useHypothesesQuery } from "./hypothesis";
import { useMemoryFeedQuery, useMemoryTimelineBoundsQuery } from "./memory-feed-item";
import { useSearchEntitiesQuery } from "./memory-graph";

const { failed } = vi.hoisted(() => ({ failed: () => Promise.resolve({ data: undefined, error: { detail: "boom" } }) }));
vi.mock("@myguyze/ze-client", () => ({
  searchEntities: failed,
  getContactsPage: failed,
  getMemoryFeed: failed,
  getMemoryTimelineBounds: failed,
  listHypotheses: failed,
  getMemoryGraph: failed,
  reviewFacts: failed,
  setHypothesisFeedback: failed,
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

describe("a failed API call is an error, not an empty result", () => {
  it.each([
    ["entity search", () => useSearchEntitiesQuery("ada")],
    ["contacts page", () => useContactsPageQuery()],
    ["memory feed", () => useMemoryFeedQuery({ type: "all" })],
    ["timeline bounds", () => useMemoryTimelineBoundsQuery()],
    ["hypotheses", () => useHypothesesQuery({ entityId: "e1" })],
  ])("%s", async (_name, hook) => {
    const { result } = renderHook(hook as () => { isError: boolean }, { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
