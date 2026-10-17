import type { GoalListItem, HeldWriteOut, LoopListItem } from "@myguyze/ze-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { buildDecisions } from "@/pages/world/lib/decisions";
import { usePendingConfirms, type PendingConfirm } from "@/features/respond-to-confirmation";
import { useGateFlights } from "@/features/answer-gate/model/gate-flights";
import { NeedsYou } from "./NeedsYou";

const m = vi.hoisted(() => ({
  send: vi.fn(),
  connected: true,
  frames: {} as Record<string, (f: unknown) => void>,
  decideHeldWrite: vi.fn(),
  confirmLoop: vi.fn(),
  dropLoop: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("@/shared/api", () => ({
  send: m.send,
  useFrame: (type: string, handler: (f: unknown) => void) => {
    m.frames[type] = handler;
  },
  useWsStore: (sel: (s: unknown) => unknown) => sel({ isConnected: m.connected, setThreadThinking: vi.fn() }),
}));
vi.mock("@/entities/session", () => ({ useSession: (sel: (s: { threadId: string }) => unknown) => sel({ threadId: "t-1" }) }));
vi.mock("@myguyze/ze-client", async (orig) => ({ ...(await orig<typeof import("@myguyze/ze-client")>()), decideHeldWrite: m.decideHeldWrite, confirmLoop: m.confirmLoop, dropLoop: m.dropLoop }));
vi.mock("react-router-dom", async (orig) => ({ ...(await orig<typeof import("react-router-dom")>()), useNavigate: () => m.navigate }));

const now = new Date("2026-10-17T12:00:00Z");

const held = { request_id: "req-1", source: "workflow", source_name: "Weekly summary", owner_ref: "wf", status: "open", created_at: "2026-10-17T08:00:00Z", expires_at: null, items: [{ item_id: "i", effect_phrase: "Send the summary", summary: "" }] } as unknown as HeldWriteOut;
const goal = { id: "g1", title: "Ship v1", status: "awaiting_gate", gate_id: "gate1", gate_title: "Review the plan", gate_open_since: "2026-10-17T07:00:00Z" } as GoalListItem;
const loop = { id: "l1", title: "Learn Rust", state: "suspected", created_at: "2026-10-17T06:00:00Z" } as LoopListItem;
const pending: PendingConfirm = { id: "c1", threadId: "t-7", kind: "write", round: 1, title: "Send this reply?", items: [{ item_id: "x", effect_phrase: "Email Ana", summary: "" }] as PendingConfirm["items"], source: null, expiresAt: null, actions: [], submitted: false };

function setup(over: { offline?: boolean; focus?: { kind: string; id: string } | null; onChatAbout?: (...a: unknown[]) => void; loading?: boolean; error?: boolean } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const decisions = buildDecisions({ held: [held], goals: [goal], loops: [loop], pendingByThread: usePendingConfirms.getState().byThread });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NeedsYou decisions={decisions} loading={over.loading ?? false} error={over.error ?? false} now={now} offline={over.offline ?? false} focus={over.focus ?? null} onChatAbout={over.onChatAbout as never} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NeedsYou", () => {
  beforeEach(() => {
    m.send.mockReset().mockReturnValue(true);
    m.connected = true;
    m.decideHeldWrite.mockReset().mockResolvedValue({ data: {} });
    m.confirmLoop.mockReset().mockResolvedValue({ data: { id: "l1", state: "active" } });
    m.dropLoop.mockReset().mockResolvedValue({ data: { id: "l1", state: "dropped" } });
    m.navigate.mockReset();
    useGateFlights.setState({ flights: {}, awaiting: {}, errors: {} });
    usePendingConfirms.setState({ byThread: { "t-7": [pending] } });
  });

  it("held write: Approve and Deny call the held-write mutation", async () => {
    setup();
    const card = within(screen.getByTestId("held-write-req-1"));
    fireEvent.click(card.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(m.decideHeldWrite).toHaveBeenCalledWith({ path: { request_id: "req-1" }, body: { choice: "approve", edits: {} } }));
    fireEvent.click(card.getByRole("button", { name: "Deny" }));
    await waitFor(() => expect(m.decideHeldWrite).toHaveBeenLastCalledWith({ path: { request_id: "req-1" }, body: { choice: "deny", edits: {} } }));
  });

  it("gate: Proceed and Stop send the action frame and disable the row until the gate leaves", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
    expect(m.send).toHaveBeenCalledWith({ type: "action", payload: "goal:approve:gate1", thread_id: "t-1" });
    await waitFor(() => expect((screen.getByRole("button", { name: "Stop" }) as HTMLButtonElement).disabled).toBe(true));
    expect((screen.getByRole("button", { name: "Proceed" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("gate: Redirect sends the frame, then chats about the gate; the row then awaits instructions with Proceed and Stop enabled", async () => {
    const onChatAbout = vi.fn();
    setup({ onChatAbout });
    fireEvent.click(screen.getByRole("button", { name: "Redirect" }));
    expect(m.send).toHaveBeenCalledWith({ type: "action", payload: "goal:redirect:gate1", thread_id: "t-1" });
    expect(onChatAbout).toHaveBeenCalledWith({ kind: "goal_gate", id: "gate1", parent_id: "g1" }, null);
    act(() => m.frames.message({ type: "message", message: { thread_id: "t-1" } }));
    expect(await screen.findByText("Waiting for your instructions")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Proceed" }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: "Stop" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("gate: an error frame shows the error line and re-enables the row", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
    act(() => m.frames.error({ type: "error", thread_id: "t-1", detail: "Checkpoint not found." }));
    expect(await screen.findByText("Checkpoint not found.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Stop" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("suspected loop: Yes, track it and Drop call the loop transition", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Yes, track it" }));
    await waitFor(() => expect(m.confirmLoop).toHaveBeenCalledWith({ path: { loop_id: "l1" } }));
    fireEvent.click(screen.getByRole("button", { name: "Drop" }));
    await waitFor(() => expect(m.dropLoop).toHaveBeenCalledWith({ path: { loop_id: "l1" } }));
  });

  it("chat confirmation: Approve responds on that thread, Open navigates to it", () => {
    setup();
    const row = screen.getByText("Send this reply?").closest(".row") as HTMLElement;
    fireEvent.click(Array.from(row.querySelectorAll("button")).find((b) => b.textContent === "Approve")!);
    expect(m.send).toHaveBeenCalledWith(expect.objectContaining({ type: "confirm", id: "c1", choice: "approve", thread_id: "t-7" }));
    fireEvent.click(Array.from(row.querySelectorAll("button")).find((b) => b.textContent === "Open")!);
    expect(m.navigate).toHaveBeenCalledWith("/ask/t-7");
  });

  it("offline disables every action", () => {
    setup({ offline: true });
    const actions = screen.getAllByRole("button").filter((b) => ["Approve", "Deny", "Proceed", "Stop", "Redirect", "Yes, track it", "Drop"].includes(b.textContent ?? ""));
    expect(actions.length).toBeGreaterThanOrEqual(7);
    for (const b of actions) expect((b as HTMLButtonElement).disabled, b.textContent ?? "").toBe(true);
    expect(screen.getByText("Ze is offline.")).toBeTruthy();
  });

  it("highlights the row named by focus", () => {
    const { container } = setup({ focus: { kind: "held_write", id: "req-1" } });
    expect(container.querySelector('[data-highlighted="true"]')).not.toBeNull();
  });

  it("shows the empty, loading and error states", () => {
    const empty = render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <NeedsYou decisions={[]} loading={false} error={false} now={now} offline={false} focus={null} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(empty.getByText("Nothing waiting on you.")).toBeTruthy();
    empty.unmount();
    setup({ error: true });
    expect(screen.getByRole("alert").textContent).toContain("Couldn't read");
  });
});
