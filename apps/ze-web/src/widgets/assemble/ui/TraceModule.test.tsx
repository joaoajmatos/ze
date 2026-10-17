import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";

vi.mock("@/features/trace-state", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/features/trace-state")>()), useSessionTraces: () => false }));
vi.mock("@/entities/message-feedback", () => ({
  useMessageFeedbackQuery: () => ({ byId: new Map([["m1", { current: null, history: [], retry: null, rollback: { state: "partial", entries: [{ entry_id: "e", tool: "t", effect_phrase: "set a reminder", outcome: "undone" }] } }]]) }),
  useSetMessageFeedbackMutation: () => ({ mutate: vi.fn() }),
}));

import { useTraceStore } from "@/features/trace-state";
import { emptyThread, useConversation } from "@/entities/conversation";
import { richTrace } from "../lib/instruments/fixtures";
import { TraceModule } from "./TraceModule";

const T = "t1";
let mm: ReturnType<typeof mockMatchMedia>;
const mount = (props = {}) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TraceModule threadId={T} {...props} />
    </QueryClientProvider>,
  );

beforeEach(() => {
  mm = mockMatchMedia({ "(prefers-reduced-motion: reduce)": false, "(max-width: 1023px)": false });
  const reply = { id: "m1", role: "assistant" as const, text: "hi", components: [], read: true, thread_id: T, created_at: "2026-10-18T10:00:00Z" };
  useConversation.setState({ byThread: { [T]: { ...emptyThread(), historyLoaded: true, messages: [reply] } } });
  useTraceStore.setState({ byThread: {} });
  useTraceStore.getState().commitPendingTrace(richTrace({ thread_id: T, message_id: "m1", sources: [{ url: "https://example.com/a", title: "A page" }] }));
});
afterEach(() => mm.restore());

describe("TraceModule", () => {
  it("has the head, the Signal path, one collapsed line per instrument with its readout, then the rows", () => {
    mount();
    expect(screen.getByRole("region", { name: "trace" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Reply feedback" })).toBeInTheDocument();
    expect(screen.getByText("Asked from · Doing › Goal · Run 5k")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Signal path" })).toBeInTheDocument();
    for (const [name, readout] of [["Routing", /companion · 72%/], ["Memory", "5 from memory"], ["Tools", "5 calls"], ["Reversal", "1 undone"]] as const) {
      const button = screen.getByRole("button", { name: new RegExp(`^${name}`) });
      expect(button).toHaveAttribute("aria-expanded", "false");
      expect(button).toHaveTextContent(readout as never);
    }
    expect(screen.getByRole("region", { name: "Sources" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Screen lookups" })).toBeInTheDocument();
  });

  it("opens an instrument on click and closes it again", () => {
    mount();
    const tools = screen.getByRole("button", { name: /^Tools/ });
    fireEvent.click(tools);
    expect(tools).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("order and duration per lane; start times not recorded")).toBeInTheDocument();
    fireEvent.click(tools);
    expect(tools).toHaveAttribute("aria-expanded", "false");
  });

  it("opens the section 'Why?' asked for", () => {
    mount({ openSection: "tools", highlight: ["get_goals"] });
    expect(screen.getByRole("button", { name: /^Tools/ })).toHaveAttribute("aria-expanded", "true");
  });

  it("hides the memory constellation while the turn streams and shows the live signal", () => {
    useConversation.setState({ byThread: { [T]: { ...emptyThread(), historyLoaded: true, turn: { phase: "thinking", typingText: null, streamingText: "", activityAt: 1, lastSent: { text: "x", context: {}, at: 1000 } } } } });
    useTraceStore.getState().mergePartialTrace({ thread_id: T, agent: "companion", memory_chunks: [{ text: "a", score: 0.9, source: "fact", extraction_confidence: null }] });
    mount();
    expect(screen.queryByRole("button", { name: /^Memory/ })).toBeNull();
    expect(document.querySelector("[data-stage=memory]")).toHaveTextContent("1 chunk");
  });

  it("says so when there is no trace", () => {
    useTraceStore.setState({ byThread: {} });
    mount();
    expect(screen.getByText("No trace for this reply.")).toBeInTheDocument();
  });
});
