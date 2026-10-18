import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

const failing = vi.hoisted(() => vi.fn(async () => ({ data: undefined, error: { detail: "boom" } })));
vi.mock("@myguyze/ze-client", () => ({
  listWorkflowExecutions: failing,
  listWorkflowRevisions: failing,
  getWorkflow: failing,
  getWorkflowExecution: failing,
}));

import { useLiveExecutionQuery } from "./useLiveExecutionQuery";
import { useWorkflowDetailQuery } from "./useWorkflowDetailQuery";
import { useWorkflowExecutionsQuery } from "./useWorkflowExecutionsQuery";
import { useWorkflowRevisionsQuery } from "./useWorkflowRevisionsQuery";

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
);

describe("workflow queries throw the client error so isError works", () => {
  it.each<[string, () => { isError: boolean }]>([
    ["executions", () => useWorkflowExecutionsQuery("w1")],
    ["revisions", () => useWorkflowRevisionsQuery("w1")],
    ["detail", () => useWorkflowDetailQuery("w1")],
    ["live execution", () => useLiveExecutionQuery("w1", "e1")],
  ])("%s", async (_name, hook) => {
    const { result } = renderHook(hook, { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
