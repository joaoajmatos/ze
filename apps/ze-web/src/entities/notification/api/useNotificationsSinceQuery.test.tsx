import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useNotificationsSinceQuery } from "./useNotificationsSinceQuery";

const { listNotifications } = vi.hoisted(() => ({ listNotifications: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ listNotifications }));

describe("useNotificationsSinceQuery", () => {
  beforeEach(() => {
    listNotifications.mockReset();
    listNotifications.mockResolvedValue({ data: { items: [{ id: "n1" }], next_cursor: null } });
  });

  it("lists with since and limit 50, never under the ['notifications'] prefix, never marking read", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useNotificationsSinceQuery("2026-10-16T00:00:00Z"), { wrapper });
    await waitFor(() => expect(result.current.data).toHaveLength(1));
    expect(listNotifications).toHaveBeenCalledWith({ query: { since: "2026-10-16T00:00:00Z", limit: 50, mark_read: false } });
    const keys = queryClient.getQueryCache().getAll().map((q) => q.queryKey);
    expect(keys).toEqual([["notifications-since", "2026-10-16T00:00:00Z"]]);
  });
});
