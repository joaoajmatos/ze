import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { useLoopTransitionMutation } from "./useLoopTransitionMutation";

const { confirmLoop, closeLoop, dropLoop } = vi.hoisted(() => ({
  confirmLoop: vi.fn(),
  closeLoop: vi.fn(),
  dropLoop: vi.fn(),
}));
vi.mock("@myguyze/ze-client", () => ({ confirmLoop, closeLoop, dropLoop }));

describe("useLoopTransitionMutation", () => {
  it("invalidates every loop key, the loop detail and the priority snapshot", async () => {
    closeLoop.mockResolvedValue({ data: { id: "l1", state: "closed" } });
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useLoopTransitionMutation(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ loopId: "l1", kind: "close" });
    });
    await waitFor(() => expect(invalidate).toHaveBeenCalled());
    const keys = invalidate.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(["loops"]);
    expect(keys).toContainEqual(["priority-snapshot"]);
    expect(keys).toContainEqual(["loop-detail", "l1"]);
    expect(closeLoop).toHaveBeenCalledWith({ path: { loop_id: "l1" } });
  });
});
