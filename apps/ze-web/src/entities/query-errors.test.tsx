import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCostAnomaliesQuery } from "./cost-entry/api/useCostAnomaliesQuery";
import { useCostsQuery } from "./cost-entry/api/useCostsQuery";
import { useDataDomainsQuery } from "./data-domain/api/useDataDomainsQuery";
import { useMemoryActivityQuery } from "./memory-feed-item/api/useMemoryActivityQuery";
import { useMessageTraceQuery } from "./message-trace/api/useMessageTraceQuery";
import { useNotificationsQuery } from "./notification/api/useNotificationsQuery";

const sdk = vi.hoisted(() => ({
  getCostAnomalies: vi.fn(),
  getCostSummary: vi.fn(),
  listDataDomains: vi.fn(),
  getMemoryActivity: vi.fn(),
  getMessageTrace: vi.fn(),
  listNotifications: vi.fn(),
}));
vi.mock("@myguyze/ze-client", () => sdk);

function wrap() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("queries throw when the client reports an error", () => {
  beforeEach(() => {
    for (const fn of Object.values(sdk)) fn.mockReset();
  });

  const failing = { data: undefined, error: { detail: "boom" } };

  const table: [string, keyof typeof sdk, () => { isError: boolean; data: unknown }][] = [
    ["costs", "getCostSummary", () => useCostsQuery()],
    ["cost anomalies", "getCostAnomalies", () => useCostAnomaliesQuery()],
    ["data domains", "listDataDomains", () => useDataDomainsQuery()],
    ["memory activity", "getMemoryActivity", () => useMemoryActivityQuery(new Date(0), new Date(1))],
    ["message trace", "getMessageTrace", () => useMessageTraceQuery("m1", true)],
    ["notifications", "listNotifications", () => useNotificationsQuery()],
  ];

  it.each(table)("%s sets isError and never resolves empty", async (_name, fn, hook) => {
    sdk[fn].mockResolvedValue(failing);
    const { result } = renderHook(hook, { wrapper: wrap() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
