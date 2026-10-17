import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useProactiveJobRunsQuery } from "./useProactiveJobRunsQuery";

const { listProactiveJobRuns } = vi.hoisted(() => ({ listProactiveJobRuns: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ listProactiveJobRuns }));

const run = (job_id: string) => ({ job_id, last_started_at: "2026-10-17T08:00:00Z", last_finished_at: "2026-10-17T08:01:00Z", last_status: "ok" });

function setup(since: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, ...renderHook(() => useProactiveJobRunsQuery(since), { wrapper }) };
}

describe("useProactiveJobRunsQuery", () => {
  beforeEach(() => {
    listProactiveJobRuns.mockReset();
    listProactiveJobRuns.mockResolvedValue({ data: [run("morning_briefing"), run("checkpoint_pruning"), run("martian_job")] });
  });

  it("passes since and keys on it", async () => {
    const { result, queryClient } = setup("2026-10-16T00:00:00Z");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(listProactiveJobRuns).toHaveBeenCalledWith({ query: { since: "2026-10-16T00:00:00Z" } });
    expect(queryClient.getQueryData(["proactive-job-runs", "2026-10-16T00:00:00Z"])).toBeDefined();
  });

  it("returns only visible jobs with a label; housekeeping and unknown ids are hidden", async () => {
    const { result } = setup("x");
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.map((r) => [r.job_id, r.label])).toEqual([["morning_briefing", "Morning briefing"]]);
  });
});
