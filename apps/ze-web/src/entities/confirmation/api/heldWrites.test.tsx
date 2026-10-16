import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useDecideHeldWriteMutation } from "./useDecideHeldWriteMutation";
import { useHeldWritesQuery } from "./useHeldWritesQuery";

const { listHeldWrites, decideHeldWrite } = vi.hoisted(() => ({
  listHeldWrites: vi.fn(),
  decideHeldWrite: vi.fn(),
}));

vi.mock("@myguyze/ze-client", () => ({ listHeldWrites, decideHeldWrite }));

const held = {
  request_id: "req-1",
  source: "workflow",
  source_name: "Weekly summary",
  owner_ref: "wf-1",
  items: [],
  status: "open",
};

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { invalidate, ...renderHook(() => ({ query: useHeldWritesQuery(), mutation: useDecideHeldWriteMutation() }), { wrapper }) };
}

describe("held writes entity", () => {
  beforeEach(() => {
    listHeldWrites.mockReset();
    decideHeldWrite.mockReset();
    listHeldWrites.mockResolvedValue({ data: { items: [held] } });
    decideHeldWrite.mockResolvedValue({ data: { ...held, status: "approved" } });
  });

  it("lists the open held writes", async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.query.data).toHaveLength(1));
    expect(result.current.query.data?.[0].request_id).toBe("req-1");
    expect(listHeldWrites).toHaveBeenCalledWith({ query: { status: "open" } });
  });

  it("throws on a list error so the query reports it", async () => {
    listHeldWrites.mockResolvedValue({ error: { detail: "boom" } });
    const { result } = setup();
    await waitFor(() => expect(result.current.query.isError).toBe(true));
  });

  it("posts the decision with edits and refreshes held writes and notifications", async () => {
    const { result, invalidate } = setup();
    await act(async () => {
      await result.current.mutation.mutateAsync({
        requestId: "req-1",
        choice: "approve",
        edits: { c1: "new body" },
      });
    });
    expect(decideHeldWrite).toHaveBeenCalledWith({
      path: { request_id: "req-1" },
      body: { choice: "approve", edits: { c1: "new body" } },
    });
    const keys = invalidate.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
    expect(keys).toContain("held-writes");
    expect(keys).toContain("notifications");
  });

  it("rejects when the server answers 409", async () => {
    decideHeldWrite.mockResolvedValue({ error: { detail: "not open" } });
    const { result } = setup();
    await expect(
      act(async () => {
        await result.current.mutation.mutateAsync({ requestId: "req-1", choice: "deny" });
      }),
    ).rejects.toBeTruthy();
  });
});
