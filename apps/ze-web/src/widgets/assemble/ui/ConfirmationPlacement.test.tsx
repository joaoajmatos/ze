import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const sendMock = vi.hoisted(() => vi.fn((_f: unknown) => true));
vi.mock("@/shared/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/shared/api")>()), send: sendMock }));

import { usePendingConfirms, toPending } from "@/features/respond-to-confirmation";
import { useConversation } from "@/entities/conversation";
import { useSession } from "@/entities/session";
import { ConfirmationPlacement } from "./ConfirmationPlacement";

const T = "t1";
const frame = (over: Record<string, unknown> = {}) =>
  ({
    type: "confirm_request",
    id: "r1",
    thread_id: T,
    kind: "write",
    round: 1,
    title: "Ze needs your OK",
    items: [
      { item_id: "c1", agent: "messenger", tool: "send_email", effect_phrase: "send an email", summary: "To Ana", conflict: null, editable_field: "body", proposed_text: "Hi Ana" },
    ],
    source: null,
    expires_at: null,
    actions: [
      { label: "Approve", value: "approve", style: "primary" },
      { label: "Deny", value: "deny", style: "secondary" },
    ],
    ...over,
  }) as never;
const open = (f = frame(), thread = T) => act(() => usePendingConfirms.getState().upsert(toPending(f, thread)));

beforeEach(() => {
  sendMock.mockClear();
  usePendingConfirms.setState({ byThread: {} });
  useConversation.setState({ byThread: {} });
  useSession.setState({ threadId: T });
});

describe("ConfirmationPlacement", () => {
  it("round-trips an edited write: approve sends the edit, deny sends none", () => {
    render(<ConfirmationPlacement threadId={T} />);
    open();
    fireEvent.change(screen.getByLabelText("Edit body"), { target: { value: "Hi Ana, sorry" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(sendMock).toHaveBeenCalledWith({ type: "confirm", id: "r1", choice: "approve", thread_id: T, edits: { c1: "Hi Ana, sorry" } });
  });

  it("sends deny", () => {
    render(<ConfirmationPlacement threadId={T} />);
    open();
    fireEvent.click(screen.getByRole("button", { name: "Deny" }));
    expect(sendMock).toHaveBeenCalledWith({ type: "confirm", id: "r1", choice: "deny", thread_id: T });
  });

  it("renders budget and held titles with their source", () => {
    render(<ConfirmationPlacement threadId={T} />);
    open(frame({ id: "b1", kind: "budget", title: "Spend ceiling reached", items: [], source: { kind: "goal", name: "Run 5k" } }));
    open(frame({ id: "h1", kind: "held", thread_id: null, title: "A run held a write", items: [], source: { kind: "workflow", name: "Weekly" } }), "*");
    expect(screen.getByText("Spend ceiling reached")).toBeInTheDocument();
    expect(screen.getByText("A run held a write")).toBeInTheDocument();
    expect(screen.getAllByTestId("confirm-source").map((e) => e.textContent)).toEqual(["From workflow: Weekly", "From goal: Run 5k"]);
  });

  it("shows a prompt's actions as command chips that send the action", () => {
    render(<ConfirmationPlacement threadId={T} />);
    open(frame({ id: "p1", kind: "prompt", title: "Goal gate", items: [], actions: [{ label: "Proceed", value: "goal:approve:g1" }] }));
    fireEvent.click(screen.getByRole("button", { name: /Proceed/ }));
    expect(sendMock).toHaveBeenCalledWith({ type: "action", payload: "goal:approve:g1", thread_id: T });
  });

  it("closes on confirm_cancel and shows only the given thread's confirmations", () => {
    render(<ConfirmationPlacement threadId={T} />);
    open(frame({ id: "other", title: "Elsewhere", thread_id: "t2" }), "t2");
    expect(screen.queryByText("Elsewhere")).toBeNull();
    open();
    expect(screen.getByText("Ze needs your OK")).toBeInTheDocument();
    act(() => usePendingConfirms.getState().cancel("r1"));
    expect(screen.queryByText("Ze needs your OK")).toBeNull();
  });
});
