import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ list: vi.fn(), search: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ listSessions: m.list, searchSessions: m.search }));

import { useSessionSearchQuery } from "./useSessionSearchQuery";
import { useSessionsQuery } from "./useSessionsQuery";

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

describe("session queries throw the client error", () => {
  it("sets isError when listSessions resolves {error}", async () => {
    m.list.mockResolvedValue({ error: { detail: "boom" } });
    const { result } = renderHook(() => useSessionsQuery(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("sets isError when searchSessions resolves {error}", async () => {
    m.search.mockResolvedValue({ error: { detail: "boom" } });
    const { result } = renderHook(() => useSessionSearchQuery("run"), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
