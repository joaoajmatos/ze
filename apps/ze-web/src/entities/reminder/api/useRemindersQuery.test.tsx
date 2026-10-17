import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useRemindersQuery } from "./useRemindersQuery";

const { listReminders } = vi.hoisted(() => ({ listReminders: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ listReminders }));

function setup(options?: Parameters<typeof useRemindersQuery>[0]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, ...renderHook(() => useRemindersQuery(options), { wrapper }) };
}

describe("useRemindersQuery", () => {
  beforeEach(() => {
    listReminders.mockReset();
    listReminders.mockResolvedValue({ data: [{ id: "r1", label: "Call Ana", fire_at: "2026-10-18T09:00:00Z", sent_at: null, status: "upcoming" }] });
  });

  it("passes status and limit and caches under ['reminders', status]", async () => {
    const { result, queryClient } = setup({ status: "all", limit: 100 });
    await waitFor(() => expect(result.current.data).toHaveLength(1));
    expect(listReminders).toHaveBeenCalledWith({ query: { status: "all", limit: 100 } });
    expect(queryClient.getQueryData(["reminders", "all"])).toHaveLength(1);
  });

  it("defaults the status to upcoming", async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(listReminders).toHaveBeenCalledWith({ query: { status: "upcoming", limit: undefined } });
  });

  it("throws on a list error", async () => {
    listReminders.mockResolvedValue({ error: { detail: "boom" } });
    const { result } = setup();
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
