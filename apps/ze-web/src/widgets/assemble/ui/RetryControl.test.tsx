import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ send: vi.fn((_f: unknown) => true), feedback: new Map<string, unknown>() }));
vi.mock("@/shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api")>()),
  send: m.send,
}));
vi.mock("@/features/trace-state", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/features/trace-state")>()), useSessionTraces: () => false }));
vi.mock("@/entities/message-feedback", () => ({
  useMessageFeedbackQuery: () => ({ byId: m.feedback }),
  useSetMessageFeedbackMutation: () => ({ mutate: vi.fn() }),
}));

import { useConversation } from "@/entities/conversation";
import { useSession } from "@/entities/session";
import { useWsStore } from "@/shared/api";
import { RetryControl } from "./RetryControl";

const T = "t1";
const reply = (id: string) => ({ id, role: "assistant" as const, text: id, components: [], read: true, thread_id: T, created_at: `2026-10-18T10:0${id.length}:00Z` });
const eligibility = (over = {}) => ({
  available: true,
  reason_code: null,
  reason_text: null,
  plan: [{ entry_id: "e1", tool: "create_reminder", effect_phrase: "set a reminder", undo_note: null }],
  ...over,
});
const apply = (e: Parameters<ReturnType<typeof useConversation.getState>["apply"]>[0]) => act(() => useConversation.getState().apply(e, { activeThreadId: T }));

function renderControl() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RetryControl threadId={T} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  m.send.mockClear();
  m.feedback = new Map();
  useConversation.setState({ byThread: {} });
  useSession.setState({ threadId: T });
  useWsStore.setState({ isConnected: true });
});

describe("RetryControl", () => {
  it("shows nothing without a reply", () => {
    renderControl();
    expect(screen.queryByRole("button", { name: "Retry reply" })).toBeNull();
  });

  it("asks for consent to the plan, then sends retry with confirmed_plan", () => {
    m.feedback = new Map([["a", { current: null, history: [], retry: eligibility() }]]);
    renderControl();
    apply({ type: "message", message: reply("a") });
    fireEvent.click(screen.getByRole("button", { name: "Retry reply" }));
    expect(screen.getByText("set a reminder")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(m.send).toHaveBeenCalledWith({ type: "retry", message_id: "a", thread_id: T, confirmed_plan: ["e1"] });
  });

  it("is disabled with its reason when history is unavailable", () => {
    m.feedback = new Map([["a", { current: null, history: [], retry: eligibility({ available: false, plan: [], reason_text: "Ze cannot tell what this reply did." }) }]]);
    renderControl();
    apply({ type: "message", message: reply("a") });
    expect(screen.getByRole("button", { name: "Retry reply" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByTestId("retry-reason")).toHaveTextContent("Ze cannot tell what this reply did.");
  });

  it("shows the outcome of a failed retry, and a rollback notice from the reply's record", () => {
    m.feedback = new Map([["a", { current: null, history: [], retry: eligibility({ plan: [] }), rollback: { state: "partial", entries: [{ entry_id: "e1", tool: "t", effect_phrase: "set a reminder", outcome: "undone" }] } }]]);
    renderControl();
    apply({ type: "message", message: reply("a") });
    apply({ type: "error", thread_id: T, detail: "x", code: "retry_failed" });
    expect(screen.getByText("Retry failed. The original reply is unchanged.")).toBeInTheDocument();
    expect(screen.getByTestId("rollback-notice")).toBeInTheDocument();
  });

  it("offers Cancel when the server says it is still working", () => {
    renderControl();
    apply({ type: "message", message: reply("a") });
    apply({ type: "sent", threadId: T, text: "hi", context: {} });
    apply({ type: "error", thread_id: T, detail: "Ze is still working on the last one.", code: "busy" });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(m.send).toHaveBeenCalledWith({ type: "command", name: "cancel", thread_id: T });
  });
});
