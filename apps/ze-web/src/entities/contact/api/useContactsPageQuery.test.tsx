import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/shared/lib";
import { useContactsPageQuery } from "./useContactsPageQuery";

vi.mock("@myguyze/ze-client", () => ({ getContactsPage: () => Promise.resolve({ data: { title: "Contacts", tree: [] } }) }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

describe("useContactsPageQuery", () => {
  it("returns the contacts tree page", async () => {
    const { result } = renderHook(() => useContactsPageQuery(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual({ title: "Contacts", tree: [] }));
  });

  it("has a stable key", () => {
    expect(queryKeys.contactsPage).toEqual(["contacts-page"]);
  });
});
