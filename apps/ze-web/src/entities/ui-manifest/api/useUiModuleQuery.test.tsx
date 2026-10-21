import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/shared/lib";

const { getUiModule } = vi.hoisted(() => ({ getUiModule: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ getUiModule }));

import { useUiModuleQuery } from "./useUiModuleQuery";

function setup() {
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { client, wrapper };
}

describe("useUiModuleQuery", () => {
  it("keys the query by module and subject and sends the subject fields", async () => {
    getUiModule.mockResolvedValue({ data: { module_id: "x.facet", applies: true, components: [], ui_version: "2.0" } });
    const { client, wrapper } = setup();
    const subject = { kind: "entity" as const, id: "e-1" };
    const { result } = renderHook(() => useUiModuleQuery("x.facet", subject), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getUiModule).toHaveBeenCalledWith({
      path: { module_id: "x.facet" },
      query: { subject_kind: "entity", subject_id: "e-1", parent_id: undefined },
    });
    expect(client.getQueryData(queryKeys.uiModule("x.facet", "entity:e-1:"))).toBeDefined();
  });

  it("throws the server's plain line on failure", async () => {
    getUiModule.mockResolvedValue({ data: undefined, error: { detail: "News took too long." } });
    const { wrapper } = setup();
    const { result } = renderHook(() => useUiModuleQuery("x.facet", { kind: "none" }), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("News took too long.");
  });
});
