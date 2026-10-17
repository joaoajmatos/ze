import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useLatestExecutionsQuery } from "./useLatestExecutionsQuery";

const { listWorkflowExecutions } = vi.hoisted(() => ({ listWorkflowExecutions: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ listWorkflowExecutions }));

const exec = (id: string) => ({ id, status: "succeeded" });

describe("useLatestExecutionsQuery", () => {
  beforeEach(() => {
    listWorkflowExecutions.mockReset();
    listWorkflowExecutions.mockImplementation(async ({ path }: { path: { workflow_id: string } }) => ({
      data: Array.from({ length: 8 }, (_, i) => exec(`${path.workflow_id}-${i}`)),
    }));
  });

  function setup(ids: string[]) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    return { queryClient, ...renderHook(() => useLatestExecutionsQuery(ids), { wrapper }) };
  }

  it("queries at most 10 workflows and keeps the latest 5 runs of each", async () => {
    const ids = Array.from({ length: 12 }, (_, i) => `w${i}`);
    const { result, queryClient } = setup(ids);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(listWorkflowExecutions).toHaveBeenCalledTimes(10);
    expect(Object.keys(result.current.byWorkflow)).toHaveLength(10);
    expect(result.current.byWorkflow["w0"]).toHaveLength(5);
    expect(queryClient.getQueryData(["workflow-executions", "w0"])).toBeDefined();
  });

  it("reports an error when any workflow fails", async () => {
    listWorkflowExecutions.mockRejectedValueOnce(new Error("x"));
    const { result } = setup(["w0", "w1"]);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe(true);
  });
});
