import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useContactsPageQuery } from "./contact";
import { useCostAnomaliesQuery } from "./cost-entry/api/useCostAnomaliesQuery";
import { useCostsQuery } from "./cost-entry/api/useCostsQuery";
import { useDataDomainsQuery } from "./data-domain/api/useDataDomainsQuery";
import { useHypothesesQuery, useHypothesisFeedbackMutation } from "./hypothesis";
import { useMemoryFeedQuery, useMemoryTimelineBoundsQuery, useReviewFactMutation } from "./memory-feed-item";
import { useMemoryActivityQuery } from "./memory-feed-item/api/useMemoryActivityQuery";
import { useSearchEntitiesQuery } from "./memory-graph";
import { useMessageTraceQuery } from "./message-trace/api/useMessageTraceQuery";
import { useNotificationsQuery } from "./notification/api/useNotificationsQuery";

const sdk = vi.hoisted(() => ({
  searchEntities: vi.fn(),
  getContactsPage: vi.fn(),
  getMemoryFeed: vi.fn(),
  getMemoryTimelineBounds: vi.fn(),
  listHypotheses: vi.fn(),
  getMemoryGraph: vi.fn(),
  reviewFacts: vi.fn(),
  setHypothesisFeedback: vi.fn(),
  getCostAnomalies: vi.fn(),
  getCostSummary: vi.fn(),
  listDataDomains: vi.fn(),
  getMemoryActivity: vi.fn(),
  getMessageTrace: vi.fn(),
  listNotifications: vi.fn(),
}));
vi.mock("@myguyze/ze-client", () => sdk);

const failing = { data: undefined, error: { detail: "boom" } };

beforeEach(() => {
  for (const fn of Object.values(sdk)) fn.mockReset().mockResolvedValue(failing);
});

function wrap() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("a failed API call is an error, not an empty result", () => {
  it.each([
    ["entity search", () => useSearchEntitiesQuery("ada")],
    ["contacts page", () => useContactsPageQuery()],
    ["memory feed", () => useMemoryFeedQuery({ type: "all" })],
    ["timeline bounds", () => useMemoryTimelineBoundsQuery()],
    ["hypotheses", () => useHypothesesQuery({ entityId: "e1" })],
  ])("%s", async (_name, hook) => {
    const { result } = renderHook(hook as () => { isError: boolean }, { wrapper: wrap() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("a failed review or feedback is an error, not a success", () => {
  it("review rejects when the API returns an error", async () => {
    const { result } = renderHook(() => useReviewFactMutation({ type: "all" }), { wrapper: wrap() });
    result.current.mutate([] as never);
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("hypothesis feedback rejects when the API returns an error", async () => {
    const { result } = renderHook(() => useHypothesisFeedbackMutation(), { wrapper: wrap() });
    result.current.mutate({ hypothesisId: "h1", feedback: "confirmed" } as never);
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("queries throw when the client reports an error (phase 193)", () => {
  const table: [string, () => { isError: boolean; data: unknown }][] = [
    ["costs", () => useCostsQuery()],
    ["cost anomalies", () => useCostAnomaliesQuery()],
    ["data domains", () => useDataDomainsQuery()],
    ["memory activity", () => useMemoryActivityQuery(new Date(0), new Date(1))],
    ["message trace", () => useMessageTraceQuery("m1", true)],
    ["notifications", () => useNotificationsQuery()],
  ];

  it.each(table)("%s sets isError and never resolves empty", async (_name, hook) => {
    const { result } = renderHook(hook, { wrapper: wrap() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
