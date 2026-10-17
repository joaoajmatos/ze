import type { WsInboundFrame } from "@myguyze/ze-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode, useEffect, useRef, type ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Handler = (f: WsInboundFrame) => void;
const mocks = vi.hoisted(() => ({
  handlers: new Map<string, Set<(f: unknown) => void>>(),
  send: vi.fn((_frame: unknown) => true),
  history: [] as unknown[],
}));

vi.mock("@/shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api")>();
  return {
    ...actual,
    send: mocks.send,
    useFrame: (type: string, handler: Handler) => {
      const ref = useRef(handler);
      ref.current = handler;
      useEffect(() => {
        const fn = (f: unknown) => ref.current(f as WsInboundFrame);
        if (!mocks.handlers.has(type)) mocks.handlers.set(type, new Set());
        mocks.handlers.get(type)!.add(fn);
        return () => void mocks.handlers.get(type)?.delete(fn);
      }, [type]);
    },
  };
});

vi.mock("@myguyze/ze-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@myguyze/ze-client")>();
  return { ...actual, listMessages: vi.fn(async () => ({ data: mocks.history })) };
});

import { useAskOverlay } from "@/features/ask-bar";
import { usePendingConfirms } from "@/features/respond-to-confirmation";
import { useSession } from "@/entities/session";
import { useWsStore } from "@/shared/api";
import { AskOverlay } from "./AskOverlay";

const ROUTE = { screen: "doing.workflows", workflow_id: "w1", execution_id: "e1" };

function emit(frame: unknown) {
  act(() => mocks.handlers.get((frame as { type: string }).type)?.forEach((h) => h(frame)));
}

const msg = (id: string, role: string, text: string, thread = "t1") => ({
  id,
  role,
  text,
  components: [],
  read: true,
  thread_id: thread,
  created_at: new Date().toISOString(),
});

function Where() {
  return <output data-testid="where">{useLocation().pathname}</output>;
}

function setup(path = "/doing/workflows/w1", children: ReactNode = null, strict = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Where />
        <AskOverlay />
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  );
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
}

const sentMessages = () => mocks.send.mock.calls.map((c) => c[0] as unknown as Record<string, unknown>).filter((f) => f.type === "message");

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  mocks.handlers.clear();
  mocks.send.mockClear();
  mocks.send.mockReturnValue(true);
  mocks.history = [];
  useAskOverlay.getState().reset();
  usePendingConfirms.setState({ byThread: {} });
  useSession.setState({ threadId: "t1" });
  useWsStore.setState({ isConnected: true, thinkingThreads: {}, typingTextThreads: {} });
});
afterEach(() => vi.restoreAllMocks());

describe("AskOverlay", () => {
  it("sends one message frame on the selected thread with the queued item's context, location unchanged", async () => {
    setup();
    act(() => void useAskOverlay.getState().submit("why did this run fail?", ROUTE));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
    expect(sentMessages()[0]).toMatchObject({ type: "message", text: "why did this run fail?", thread_id: "t1", context: ROUTE });
    expect(screen.getByTestId("where")).toHaveTextContent("/doing/workflows/w1");
    expect(useAskOverlay.getState().outbox).toBeNull();
  });

  it("uses the context queued with the item, not the route at drain time", async () => {
    setup("/mind");
    act(() => void useAskOverlay.getState().submit("x", ROUTE));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
    expect(sentMessages()[0].context).toEqual(ROUTE);
  });

  it("sends exactly once per item under StrictMode", async () => {
    setup("/", null, true);
    act(() => void useAskOverlay.getState().submit("once", ROUTE));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(sentMessages()).toHaveLength(1);
  });

  it("keeps the item while a turn is in flight and sends it once the turn ends", async () => {
    useWsStore.setState({ thinkingThreads: { t1: true } });
    setup();
    act(() => void useAskOverlay.getState().submit("later", ROUTE));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(sentMessages()).toHaveLength(0);
    expect(useAskOverlay.getState().outbox?.text).toBe("later");
    act(() => useWsStore.setState({ thinkingThreads: { t1: false } }));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
  });

  it("keeps the item while offline and sends it when the socket returns", async () => {
    useWsStore.setState({ isConnected: false });
    setup();
    act(() => void useAskOverlay.getState().submit("offline", ROUTE));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(sentMessages()).toHaveLength(0);
    expect(useAskOverlay.getState().outbox).not.toBeNull();
    act(() => useWsStore.setState({ isConnected: true }));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
  });

  it("shows only messages after the opening message, plus the streamed reply", async () => {
    mocks.history = [msg("old-1", "user", "earlier question"), msg("old-2", "assistant", "earlier answer")];
    setup();
    act(() => void useAskOverlay.getState().submit("new question", ROUTE));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
    expect(screen.queryByText("earlier answer")).not.toBeInTheDocument();
    expect(screen.getByText("new question")).toBeInTheDocument();
    emit({ type: "token", thread_id: "t1", text: "Because " });
    emit({ type: "token", thread_id: "t1", text: "the key expired" });
    expect(await screen.findByText(/Because the key expired/)).toBeInTheDocument();
    emit({ type: "message", message: msg("a-1", "assistant", "The key expired.") });
    expect(await screen.findByText("The key expired.")).toBeInTheDocument();
  });

  it("renders a pending confirmation and Approve sends confirm", async () => {
    setup();
    act(() => void useAskOverlay.getState().submit("delete it", ROUTE));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
    act(() =>
      usePendingConfirms.getState().upsert({
        id: "req-1",
        threadId: "t1",
        kind: "write",
        round: 1,
        title: "Ze needs your OK",
        items: [
          { item_id: "c1", agent: "calendar", tool: "delete_event", effect_phrase: "delete a calendar event", summary: "Dentist", conflict: null, editable_field: null, proposed_text: null },
        ],
        source: null,
        expiresAt: null,
        actions: [{ label: "Approve all", value: "approve", style: "primary" }],
        submitted: false,
      }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Approve all" }));
    expect(mocks.send).toHaveBeenCalledWith(expect.objectContaining({ type: "confirm", id: "req-1", choice: "approve", thread_id: "t1" }));
  });

  it("Open in Ask goes to the thread and closes", async () => {
    setup();
    act(() => void useAskOverlay.getState().submit("hi", ROUTE));
    fireEvent.click(await screen.findByRole("button", { name: "Open in Ask" }));
    expect(screen.getByTestId("where")).toHaveTextContent("/ask/t1");
    expect(useAskOverlay.getState().open).toBe(false);
  });

  it("New chat starts a fresh selected thread and the next frame uses it", async () => {
    setup();
    act(() => void useAskOverlay.getState().submit("first", ROUTE));
    await waitFor(() => expect(sentMessages()).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    const fresh = useSession.getState().threadId;
    expect(fresh).not.toBe("t1");
    act(() => void useAskOverlay.getState().submit("second", ROUTE));
    await waitFor(() => expect(sentMessages()).toHaveLength(2));
    expect(sentMessages()[1].thread_id).toBe(fresh);
    expect(screen.queryByText("first")).not.toBeInTheDocument();
  });

  it("Esc closes", async () => {
    setup();
    act(() => void useAskOverlay.getState().submit("hi", ROUTE));
    await screen.findByRole("button", { name: "Close" });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(useAskOverlay.getState().open).toBe(false);
  });

  it("stays open across navigation", async () => {
    function Go() {
      const loc = useLocation();
      return loc.pathname === "/" ? <a href="/mind">go</a> : null;
    }
    setup("/", <Go />);
    act(() => void useAskOverlay.getState().submit("hi", ROUTE));
    await screen.findByRole("button", { name: "Open in Ask" });
    expect(useAskOverlay.getState().open).toBe(true);
  });

  it("is hidden on /ask", () => {
    setup("/ask");
    act(() => useAskOverlay.getState().openWith(null, null));
    expect(screen.queryByRole("button", { name: "Open in Ask" })).not.toBeInTheDocument();
  });
});
