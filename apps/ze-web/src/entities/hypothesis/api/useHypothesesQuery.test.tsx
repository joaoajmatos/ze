import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useHypothesesQuery } from "./useHypothesesQuery";

const { listHypotheses } = vi.hoisted(() => ({ listHypotheses: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ listHypotheses }));

function setup(options?: Parameters<typeof useHypothesesQuery>[0]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, ...renderHook(() => useHypothesesQuery(options), { wrapper }) };
}

describe("useHypothesesQuery", () => {
  beforeEach(() => {
    listHypotheses.mockReset();
    listHypotheses.mockResolvedValue({ data: [{ id: "h1", summary: "s" }] });
  });

  it("passes state, entity_id and limit; key is ['hypotheses', state, entityId]", async () => {
    const { result, queryClient } = setup({ state: "all", entityId: "e1", limit: 200 });
    await waitFor(() => expect(result.current.data).toHaveLength(1));
    expect(listHypotheses).toHaveBeenCalledWith({ query: { state: "all", entity_id: "e1", limit: 200 } });
    expect(queryClient.getQueryData(["hypotheses", "all", "e1"])).toHaveLength(1);
  });

  it("uses an empty entity segment when none is given", async () => {
    const { queryClient, result } = setup({ state: "open" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(queryClient.getQueryData(["hypotheses", "open", ""])).toHaveLength(1);
  });

  it("throws on a list error", async () => {
    listHypotheses.mockResolvedValue({ error: { detail: "boom" } });
    const { result } = setup();
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
