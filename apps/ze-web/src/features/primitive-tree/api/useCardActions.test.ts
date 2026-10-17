import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { loopMutate, heldMutate, navigate, send, showNotice } = vi.hoisted(() => ({
  loopMutate: vi.fn(() => Promise.resolve()),
  heldMutate: vi.fn(() => Promise.resolve()),
  navigate: vi.fn(),
  send: vi.fn(() => true),
  showNotice: vi.fn(),
}));

vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }));
vi.mock("@/entities/loop", () => ({
  useLoopTransitionMutation: () => ({ mutateAsync: loopMutate }),
}));
vi.mock("@/entities/confirmation", () => ({
  useDecideHeldWriteMutation: () => ({ mutateAsync: heldMutate }),
}));
vi.mock("@/entities/session", () => ({
  useSession: (selector: (s: { threadId: string }) => unknown) => selector({ threadId: "t-1" }),
}));
vi.mock("@/shared/api", () => ({ send }));
vi.mock("@/shared/lib", () => ({
  useSendNotice: (selector: (s: { showNotice: typeof showNotice }) => unknown) =>
    selector({ showNotice }),
}));

import { useCardActions } from "./useCardActions";

function run(intent: string, ref_id = "id-1", subject = "loop") {
  const { result } = renderHook(() => useCardActions());
  return result.current({ intent, ref_id, subject });
}

describe("useCardActions", () => {
  beforeEach(() => vi.clearAllMocks());

  it("confirm_loop confirms the loop", () => {
    run("confirm_loop");
    expect(loopMutate).toHaveBeenCalledWith({ loopId: "id-1", kind: "confirm" });
  });

  it("drop_loop drops the loop", () => {
    run("drop_loop");
    expect(loopMutate).toHaveBeenCalledWith({ loopId: "id-1", kind: "drop" });
  });

  it("approve_held_write and deny_held_write decide the held write", () => {
    run("approve_held_write", "req-1", "held_write");
    expect(heldMutate).toHaveBeenCalledWith({ requestId: "req-1", choice: "approve" });
    run("deny_held_write", "req-1", "held_write");
    expect(heldMutate).toHaveBeenLastCalledWith({ requestId: "req-1", choice: "deny" });
  });

  it("approve_gate sends the goal approve action frame", () => {
    run("approve_gate", "gate-1", "goal");
    expect(send).toHaveBeenCalledWith({
      type: "action",
      payload: "goal:approve:gate-1",
      thread_id: "t-1",
    });
  });

  it("approve_gate tells the user when the socket is down and reports failure", async () => {
    send.mockReturnValueOnce(false);
    await expect(run("approve_gate", "gate-1", "goal")).resolves.toBe(false);
    expect(showNotice).toHaveBeenCalledWith("Not connected. Retry when Ze reconnects.");
  });

  it("a rejected mutation reports failure and a resolved one success", async () => {
    loopMutate.mockRejectedValueOnce(new Error("500"));
    await expect(run("confirm_loop")).resolves.toBe(false);
    await expect(run("confirm_loop")).resolves.toBe(true);
  });

  it("open navigates to the record's page", () => {
    run("open", "g-1", "goal");
    expect(navigate).toHaveBeenCalledWith("/doing/goals/g-1");
  });

  it("open selects a held write on World", () => {
    run("open", "h-1", "held_write");
    expect(navigate).toHaveBeenCalledWith("/?focus=held_write:h-1");
  });

  it("open does nothing for a subject without a page", () => {
    run("open", "p-1", "person");
    expect(navigate).not.toHaveBeenCalled();
  });
});
