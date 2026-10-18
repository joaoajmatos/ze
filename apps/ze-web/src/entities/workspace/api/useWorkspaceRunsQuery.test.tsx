import type { WorkspaceRunResponse } from "@myguyze/ze-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const listWorkspaceRuns = vi.fn();
const cancelWorkspaceRun = vi.fn();
const getWorkspace = vi.fn();
vi.mock("@myguyze/ze-client", () => ({
  listWorkspaceRuns: (...a: unknown[]) => listWorkspaceRuns(...a),
  cancelWorkspaceRun: (...a: unknown[]) => cancelWorkspaceRun(...a),
  getWorkspace: (...a: unknown[]) => getWorkspace(...a),
}));

import { useCancelWorkspaceRunMutation } from "./useCancelWorkspaceRunMutation";
import { useWorkspaceQuery } from "./useWorkspaceQuery";
import { useWorkspaceRunsQuery } from "./useWorkspaceRunsQuery";

const run = (o: Partial<WorkspaceRunResponse>) => ({ id: "r1", status: "succeeded", origin: "user", command: "ls", ...o }) as WorkspaceRunResponse;

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client,
    Wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  };
}

describe("workspace runs", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    listWorkspaceRuns.mockReset();
    cancelWorkspaceRun.mockReset();
    getWorkspace.mockReset();
    getWorkspace.mockResolvedValue({ data: { available: true, busy: false }, error: undefined });
  });
  afterEach(() => vi.useRealTimers());

  it("lists with limit 20 and polls every 5 s only while a run is in progress", async () => {
    listWorkspaceRuns.mockResolvedValue({ data: { runs: [run({ status: "in_progress" })] }, error: undefined });
    const { Wrapper } = wrapper();
    renderHook(() => useWorkspaceRunsQuery({ limit: 20 }), { wrapper: Wrapper });
    await waitFor(() => expect(listWorkspaceRuns).toHaveBeenCalledTimes(1));
    expect(listWorkspaceRuns).toHaveBeenCalledWith({ query: { limit: 20 } });
    await act(async () => { await vi.advanceTimersByTimeAsync(5100); });
    expect(listWorkspaceRuns.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("does not poll when nothing runs", async () => {
    listWorkspaceRuns.mockResolvedValue({ data: { runs: [run({})] }, error: undefined });
    const { Wrapper } = wrapper();
    renderHook(() => useWorkspaceRunsQuery({ limit: 20 }), { wrapper: Wrapper });
    await waitFor(() => expect(listWorkspaceRuns).toHaveBeenCalledTimes(1));
    await act(async () => { await vi.advanceTimersByTimeAsync(11000); });
    expect(listWorkspaceRuns).toHaveBeenCalledTimes(1);
  });

  it("throws the client error so isError works", async () => {
    listWorkspaceRuns.mockResolvedValue({ data: undefined, error: { detail: "x" } });
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useWorkspaceRunsQuery({ limit: 20 }), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("workspace status polls on the runs data", async () => {
    listWorkspaceRuns.mockResolvedValue({ data: { runs: [run({ status: "in_progress" })] }, error: undefined });
    const { Wrapper } = wrapper();
    renderHook(() => { useWorkspaceRunsQuery({ limit: 20 }); return useWorkspaceQuery(); }, { wrapper: Wrapper });
    await waitFor(() => expect(getWorkspace).toHaveBeenCalledTimes(1));
    await act(async () => { await vi.advanceTimersByTimeAsync(5100); });
    expect(getWorkspace.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

describe("useCancelWorkspaceRunMutation", () => {
  beforeEach(() => cancelWorkspaceRun.mockReset());

  it("cancels and invalidates runs and workspace", async () => {
    cancelWorkspaceRun.mockResolvedValue({ data: {}, error: undefined, response: { status: 200 } });
    const { Wrapper, client } = wrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCancelWorkspaceRunMutation(), { wrapper: Wrapper });
    let out;
    await act(async () => { out = await result.current.mutateAsync("r1"); });
    expect(cancelWorkspaceRun).toHaveBeenCalledWith({ path: { run_id: "r1" } });
    expect(out).toEqual({ outcome: "cancelled" });
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it.each([[409, "already finished"], [404, "no longer exists"]])("resolves a %s as a plain outcome", async (status, line) => {
    cancelWorkspaceRun.mockResolvedValue({ data: undefined, error: { detail: "x" }, response: { status } });
    const { Wrapper, client } = wrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCancelWorkspaceRunMutation(), { wrapper: Wrapper });
    let out;
    await act(async () => { out = await result.current.mutateAsync("r1"); });
    expect(out).toEqual({ outcome: "gone", line });
    expect(spy).toHaveBeenCalled();
  });

  it("throws other errors", async () => {
    cancelWorkspaceRun.mockResolvedValue({ data: undefined, error: { detail: "x" }, response: { status: 500 } });
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useCancelWorkspaceRunMutation(), { wrapper: Wrapper });
    await act(async () => { await expect(result.current.mutateAsync("r1")).rejects.toBeTruthy(); });
  });
});
