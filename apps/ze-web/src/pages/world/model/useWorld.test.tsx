import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LAST_SEEN_KEY } from "../lib/last-seen";
import { useWorld } from "./useWorld";

const api = vi.hoisted(() => ({
  getPrioritySnapshot: vi.fn(),
  listLoops: vi.fn(),
  listGoals: vi.fn(),
  listWorkflows: vi.fn(),
  listWorkflowExecutions: vi.fn(),
  listHeldWrites: vi.fn(),
  listReminders: vi.fn(),
  listHypotheses: vi.fn(),
  listNotifications: vi.fn(),
  listProactiveJobRuns: vi.fn(),
  getAttentionBudget: vi.fn(),
}));
vi.mock("@myguyze/ze-client", async (orig) => ({ ...(await orig<typeof import("@myguyze/ze-client")>()), ...api }));

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  return renderHook(() => useWorld(), { wrapper });
}

describe("useWorld", () => {
  beforeEach(() => {
    localStorage.clear();
    for (const fn of Object.values(api)) fn.mockReset();
    api.getPrioritySnapshot.mockResolvedValue({ data: { items: [{ source_kind: "loop", source_id: "l1", title: "Reply to Ana", displayed_rank: 1, computed_rank: 1, overridden_from_computed: false, override: null }], sources_failed: ["hypothesis"] } });
    api.listLoops.mockResolvedValue({ data: [{ id: "l1", title: "Reply to Ana", state: "drifting", claim_kind: "fact", provenance: "email", confidence: 0.6, source_inflows: [], created_at: null, updated_at: null }] });
    api.listGoals.mockResolvedValue({ data: [] });
    api.listWorkflows.mockResolvedValue({ data: [{ id: "w1", name: "Weekly" }] });
    api.listWorkflowExecutions.mockResolvedValue({ data: [{ id: "e1", status: "running" }] });
    api.listHeldWrites.mockResolvedValue({ data: { items: [] } });
    api.listReminders.mockResolvedValue({ data: [] });
    api.listHypotheses.mockResolvedValue({ data: [] });
    api.listNotifications.mockResolvedValue({ data: { items: [], next_cursor: null } });
    api.listProactiveJobRuns.mockResolvedValue({ data: [] });
    api.getAttentionBudget.mockResolvedValue({ data: { used: 1, max_per_day: 5, remaining: 4, window_hours: 24, next_slot_at: null, held_count: 0, quiet_hours_active: false } });
  });

  it("composes the parts and carries sourcesFailed from the snapshot", async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.field.loading).toBe(false));
    expect(result.current.sourcesFailed).toEqual(["hypothesis"]);
    await waitFor(() => expect(result.current.running).toBe(true));
    expect(result.current.counts).toEqual({ slipped: 1, watched: 1, waiting: 0 });
    expect(result.current.sentence).toBe("One promise slipped. I am watching one concern.");
    expect(result.current.field.data[0]).toMatchObject({ kind: "loop", slipped: true, confidence: 0.6 });
  });

  it("one failing query sets only its part's error", async () => {
    api.listHeldWrites.mockResolvedValue({ error: { detail: "boom" } });
    const { result } = setup();
    await waitFor(() => expect(result.current.decisions.error).toBe(true));
    expect(result.current.field.error).toBe(false);
    expect(result.current.away.error).toBe(false);
    expect(result.current.loops.error).toBe(false);
  });

  it.each([
    ["snapshot", "getPrioritySnapshot", "field"],
    ["goals", "listGoals", "doing"],
    ["loops", "listLoops", "loops"],
  ] as const)("a failing %s query is an error, never an empty all-clear", async (_n, fn, part) => {
    api[fn].mockResolvedValue({ error: { detail: "boom" } });
    const { result } = setup();
    await waitFor(() => expect(result.current[part].error).toBe(true));
    if (part === "field") expect(result.current.field.data).toEqual([]);
    expect(result.current.away.error).toBe(false);
  });

  it("waits for every record before the field stops loading, and names a failed record source", async () => {
    let release: (v: unknown) => void = () => {};
    api.listHypotheses.mockReturnValue(new Promise((r) => (release = r)));
    const { result } = setup();
    await waitFor(() => expect(result.current.recordsFailed).toEqual([]));
    await new Promise((r) => setTimeout(r, 50));
    expect(result.current.field.loading).toBe(true);
    release({ error: { detail: "boom" } });
    await waitFor(() => expect(result.current.field.loading).toBe(false));
    expect(result.current.recordsFailed).toEqual(["hypotheses"]);
    expect(result.current.field.error).toBe(false);
  });

  it("a failing away source blanks only away", async () => {
    api.listProactiveJobRuns.mockResolvedValue({ error: { detail: "boom" } });
    const { result } = setup();
    await waitFor(() => expect(result.current.away.error).toBe(true));
    expect(result.current.decisions.error).toBe(false);
    expect(result.current.field.error).toBe(false);
  });

  it("since for Away is the stored last-seen, sent to both away queries", async () => {
    localStorage.setItem(LAST_SEEN_KEY, "2026-10-17T08:00:00.000Z");
    const { result } = setup();
    expect(result.current.since).toEqual(new Date("2026-10-17T08:00:00.000Z"));
    await waitFor(() => expect(api.listNotifications).toHaveBeenCalled());
    expect(api.listNotifications.mock.calls[0][0].query.since).toBe("2026-10-17T08:00:00.000Z");
    await waitFor(() => expect(api.listProactiveJobRuns).toHaveBeenCalledWith({ query: { since: "2026-10-17T08:00:00.000Z" } }));
  });
});
