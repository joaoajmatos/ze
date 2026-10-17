import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/shared/lib";
import { useSearchEntitiesQuery } from "./useSearchEntitiesQuery";

const searchEntities = vi.fn();
vi.mock("@myguyze/ze-client", () => ({ searchEntities: (a: unknown) => searchEntities(a) }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

describe("useSearchEntitiesQuery", () => {
  beforeEach(() => searchEntities.mockReset());

  it("is disabled for an empty text", () => {
    const { result } = renderHook(() => useSearchEntitiesQuery("  "), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(searchEntities).not.toHaveBeenCalled();
  });

  it("searches by text and type", async () => {
    searchEntities.mockResolvedValue({ data: [{ id: "e1" }] });
    const { result } = renderHook(() => useSearchEntitiesQuery("ada", "person"), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual([{ id: "e1" }]));
    expect(searchEntities).toHaveBeenCalledWith({ query: { q: "ada", entity_type: "person", limit: 20 } });
  });

  it("keys on text and type", () => {
    expect(queryKeys.entitySearch("ada", "person")).toEqual(["entity-search", "ada", "person"]);
    expect(queryKeys.entitySearch("ada")).toEqual(["entity-search", "ada", ""]);
  });
});
