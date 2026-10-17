import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/shared/lib";
import { useHypothesesQuery } from "./useHypothesesQuery";

const listHypotheses = vi.fn().mockResolvedValue({ data: [{ id: "h1" }] });
vi.mock("@myguyze/ze-client", () => ({ listHypotheses: (a: unknown) => listHypotheses(a), setHypothesisFeedback: vi.fn() }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

describe("useHypothesesQuery", () => {
  it("passes state, entity and limit", async () => {
    const { result } = renderHook(() => useHypothesesQuery({ state: "all", entityId: "e1", limit: 5 }), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual([{ id: "h1" }]));
    expect(listHypotheses).toHaveBeenCalledWith({ query: { state: "all", entity_id: "e1", limit: 5 } });
  });

  it("keys on state and entity", () => {
    expect(queryKeys.hypotheses("open", "e1")).toEqual(["hypotheses", "open", "e1"]);
    expect(queryKeys.hypotheses("open")).toEqual(["hypotheses", "open", ""]);
  });
});
