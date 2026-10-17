import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { MessageSchema as Message } from "@myguyze/ze-client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";

const m = vi.hoisted(() => ({ resend: vi.fn(() => true) }));
vi.mock("@/features/turn-stream", () => ({ resendTurn: m.resend }));
vi.mock("@/features/trace-state", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/trace-state")>()),
  useSessionTraces: () => false,
}));
vi.mock("@/entities/message-feedback", () => ({
  useMessageFeedbackQuery: () => ({ byId: new Map([["a2", { current: null, history: [], retry: null }]]) }),
  useSetMessageFeedbackMutation: () => ({ mutate: vi.fn() }),
}));

import { emptyThread, useConversation, type ThreadState } from "@/entities/conversation";
import { usePresenceStore } from "@/entities/presence";
import { useScreenContextStore } from "@/entities/screen-context";
import { Canvas } from "./Canvas";

const T = "t1";
const msg = (id: string, role: "user" | "assistant", over: Partial<Message> = {}): Message => ({
  id,
  role,
  text: `${role} ${id}`,
  components: [],
  read: true,
  thread_id: T,
  created_at: `2026-10-18T10:0${id.length}:00Z`,
  ...over,
});
const claim = (title: string, tone?: string) => ({ type: "claim_card", title, tone, claim: { subject: "goal", ref_id: title } });

function setThread(over: Partial<ThreadState>) {
  useConversation.setState({ byThread: { [T]: { ...emptyThread(), historyLoaded: true, ...over } } });
}
function renderCanvas(props: Partial<React.ComponentProps<typeof Canvas>> = {}) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <div className="presence-orb" />
        <Canvas threadId={T} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

let mm: ReturnType<typeof mockMatchMedia>;
beforeEach(() => {
  mm = mockMatchMedia({ "(prefers-reduced-motion: reduce)": false });
  usePresenceStore.getState().reset();
  m.resend.mockClear();
  Element.prototype.animate = vi.fn(() => ({ cancel: vi.fn(), finished: Promise.resolve() })) as never;
});
afterEach(() => {
  mm.restore();
  useConversation.setState({ byThread: {} });
  vi.useRealTimers();
});

describe("Canvas", () => {
  it("renders the sentence, then one module per top-level component in order with A·NN ids", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant", { components: [claim("Run 5k"), { type: "text", content: "hello body" }] })] });
    renderCanvas();
    const mods = screen.getAllByRole("region").length ? screen.getAllByRole("region") : [];
    expect(screen.getByText("assistant a2")).toBeInTheDocument();
    const ids = [...document.querySelectorAll(".mod .idx")].map((e) => e.textContent);
    expect(ids).toEqual(["A·01", "A·02"]);
    expect(mods.length).toBeGreaterThanOrEqual(0);
    const order = [...document.querySelectorAll(".assemble-sentence, .canvas .mod")].map((e) => (e.classList.contains("assemble-sentence") ? "sentence" : "module"));
    expect(order).toEqual(["sentence", "module", "module"]);
  });

  it("labels an assistant message with no user line 'Ze, unprompted'", () => {
    setThread({ messages: [msg("a2", "assistant")] });
    renderCanvas();
    expect(screen.getByText("Ze, unprompted")).toBeInTheDocument();
  });

  it("shows 'Ze did not answer' with Resend on a failed turn, and resend adds no second user line", () => {
    setThread({
      messages: [msg("u", "user")],
      turn: { phase: "failed", typingText: null, streamingText: "", activityAt: 0, lastSent: { text: "u", context: {}, at: 1 } },
    });
    renderCanvas();
    expect(screen.getByText("Ze did not answer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resend" }));
    expect(m.resend).toHaveBeenCalledWith(T);
    expect(screen.getAllByText("user u")).toHaveLength(1);
  });

  it("puts compact thumbs on the latest reply only", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant"), msg("u3", "user"), msg("a3x", "assistant")] });
    renderCanvas();
    expect(screen.getAllByRole("button", { name: "Good reply" })).toHaveLength(1);
  });

  it("spans by type on desktop and all 12 when compact; tone follows the claim", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant", { components: [claim("Slipping", "hot"), { type: "table", headers: ["h"], rows: [["c"]] }, { type: "text", content: "t" }] })] });
    const { unmount } = renderCanvas();
    const cells = [...document.querySelectorAll(".canvas .cell")];
    expect(cells.map((c) => [...c.classList].find((k) => k.startsWith("span-")))).toEqual(["span-12", "span-4", "span-8", "span-6"]);
    expect(document.querySelectorAll(".mod.hot").length).toBe(1);
    unmount();
    renderCanvas({ compact: true });
    expect([...document.querySelectorAll(".canvas .cell")].every((c) => c.classList.contains("span-12"))).toBe(true);
  });

  it("shows streaming text while speaking", () => {
    setThread({
      messages: [msg("u", "user")],
      turn: { phase: "speaking", typingText: null, streamingText: "Hello wor", activityAt: 0, lastSent: null },
    });
    renderCanvas();
    expect(screen.getByText(/Hello wor/)).toBeInTheDocument();
  });

  it("states the AI disclosure once, under the first reply of a thread", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant"), msg("u3", "user"), msg("a3x", "assistant")] });
    renderCanvas();
    expect(screen.getAllByText("Ze is AI and can make mistakes.")).toHaveLength(1);
  });

  it("pins a module to the top and dismisses another (view state)", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant", { components: [claim("First"), claim("Second")] })] });
    renderCanvas();
    fireEvent.click(screen.getByRole("button", { name: "Pin Second" }));
    const titles = () => [...document.querySelectorAll(".canvas .mod")].map((e) => e.getAttribute("aria-label"));
    expect(titles()[0]).toBe("Second");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss First" }));
    expect(titles()).not.toContain("First");
  });

  it("renders a preset reply: headline, timeline, then claim cards", () => {
    setThread({
      messages: [msg("u", "user"), msg("a2", "assistant", { components: [{ type: "headline", text: "2 slipping" }, { type: "claim_timeline", title: "Ahead", entries: [{ title: "Pay rent" }] }, claim("A"), claim("B")] })],
    });
    renderCanvas();
    const types = [...document.querySelectorAll(".canvas .cell")].map((c) => c.getAttribute("data-type"));
    expect(types).toEqual([null, "headline", "claim_timeline", "claim_card", "claim_card"]);
  });

  it("flies a live reply's modules from the orb, with the assembling signal during the cascade", () => {
    vi.useFakeTimers();
    setThread({ historyLoaded: true, messages: [msg("u", "user")] });
    renderCanvas();
    act(() => {
      useConversation.getState().apply({ type: "message", message: msg("a2", "assistant", { components: [claim("A"), claim("B")], created_at: "2026-10-18T10:05:00Z" }) }, { activeThreadId: T });
    });
    const calls = (Element.prototype.animate as unknown as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.length).toBe(2);
    expect(JSON.stringify(calls[0][0])).toContain("transform");
    expect(calls[1][1]).toMatchObject({ delay: 80 });
    expect(usePresenceStore.getState().presence.worldSignal).toBe("assembling");
    act(() => void vi.advanceTimersByTime(2000));
    expect(usePresenceStore.getState().presence.worldSignal).toBeNull();
  });

  it("uses opacity only under reduced motion", () => {
    mm.set("(prefers-reduced-motion: reduce)", true);
    setThread({ historyLoaded: true, messages: [msg("u", "user")] });
    renderCanvas();
    act(() => {
      useConversation.getState().apply({ type: "message", message: msg("a2", "assistant", { components: [claim("A")], created_at: "2026-10-18T10:05:00Z" }) }, { activeThreadId: T });
    });
    const calls = (Element.prototype.animate as unknown as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.length).toBe(1);
    expect(JSON.stringify(calls[0][0])).not.toContain("transform");
  });

  it("does not cascade replies that were already in the history", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant", { components: [claim("A")] })] });
    renderCanvas();
    expect(Element.prototype.animate).not.toHaveBeenCalled();
    expect(within(document.body).queryByText("Ze did not answer")).toBeNull();
  });

  it("adds 'Chat about this' to a module with a claim, and not to one without", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant", { components: [claim("Run 5k"), { type: "text", content: "t" }] })] });
    const onChatAbout = vi.fn();
    renderCanvas({ onChatAbout });
    expect(screen.getAllByRole("button", { name: /Chat about/ })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Chat about Run 5k" }));
    expect(onChatAbout).toHaveBeenCalledWith({ kind: "goal", id: "Run 5k", label: "Run 5k", component: "claim_card" }, expect.any(HTMLElement));
  });

  it("publishes the canvas refs and the focused module", () => {
    setThread({ messages: [msg("u", "user"), msg("a2", "assistant", { components: [claim("Run 5k"), { type: "text", content: "t" }] })] });
    renderCanvas({ onChatAbout: vi.fn() });
    const pubs = () => [...useScreenContextStore.getState().publications.values()];
    expect(pubs().flatMap((p) => p.canvas ?? [])).toEqual([
      { index: "A·01", type: "claim_card", ref: { kind: "goal", id: "Run 5k" } },
      { index: "A·02", type: "text" },
    ]);
    fireEvent.focus(screen.getByRole("button", { name: "Pin Run 5k" }));
    expect(pubs().map((p) => p.focused_module).filter(Boolean)).toEqual(["A·01"]);
  });
});
