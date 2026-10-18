import type { WsInboundFrame } from "@myguyze/ze-client";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";

const mocks = vi.hoisted(() => ({
  glance: vi.fn(),
  sendTurn: vi.fn(() => true),
  takeOver: vi.fn(),
  handlers: new Map<string, Set<(f: unknown) => void>>(),
}));

vi.mock("@/shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api")>();
  return {
    ...actual,
    takeOver: mocks.takeOver,
    useFrame: (type: string, handler: (f: WsInboundFrame) => void) => {
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
vi.mock("@/features/invalidate-on-ws-refresh", () => ({ RefreshHandler: () => null }));
vi.mock("@/features/respond-to-confirmation", () => ({ ConfirmationFrameHandler: () => null }));
vi.mock("@/features/turn-stream", () => ({ TurnFrameHandler: () => null, sendTurn: mocks.sendTurn }));
vi.mock("@/features/trace-state", () => ({ TraceFrameHandler: () => null }));
vi.mock("./NotificationBell", () => ({ NotificationBell: () => <button type="button">Notifications</button> }));
vi.mock("@/shared/ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/ui")>()),
  NoticeBanner: () => null,
  Presence: forwardRef(function PresenceStub(props: { state: string; phrase: string; compact?: boolean; headSlot?: React.ReactNode; level?: () => number }, ref) {
    useImperativeHandle(ref, () => ({ glance: mocks.glance }), []);
    return (
      <section data-testid="presence" data-state={props.state} data-compact={String(!!props.compact)}>
        {props.phrase}
        <div data-testid="presence-head">{props.headSlot}</div>
      </section>
    );
  }),
}));

import { useAskOverlay } from "@/features/ask-bar";
import { useVoiceInput } from "@/features/voice-input";
import { usePresenceStore } from "@/entities/presence";
import { useSession } from "@/entities/session";
import { useWsStore } from "@/shared/api";
import { AppShell } from "./AppShell";

const idleVoice = { status: "idle" as const, startedAt: null, reason: null, failure: null, notice: null, pending: null };

let mm: ReturnType<typeof mockMatchMedia>;

function renderShell(path = "/", overlay?: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppShell overlay={overlay} />}>
          <Route path="*" element={<p>page</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mocks.sendTurn.mockClear();
  mm = mockMatchMedia({});
  mocks.glance.mockClear();
  mocks.handlers.clear();
  useAskOverlay.getState().reset();
  useVoiceInput.setState(idleVoice);
  usePresenceStore.getState().reset();
  useWsStore.setState({ isConnected: true, thinkingThreads: {}, typingTextThreads: {} });
});
afterEach(() => mm.restore());

describe("AppShell desktop", () => {
  it.each([
    ["/", "World"],
    ["/ask", "Ask"],
    ["/doing/goals/g1", "Doing"],
    ["/mind/11111111-1111-4111-8111-111111111111", "Mind"],
    ["/governance/settings", "Governance"],
  ])("%s marks %s as current", (path, label) => {
    renderShell(path);
    const tabs = screen.getByRole("navigation", { name: "Places" });
    const links = within(tabs).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual(["World", "Ask", "Doing", "Mind", "Governance"]);
    const current = links.filter((l) => l.getAttribute("aria-current") === "page");
    expect(current.map((l) => l.textContent)).toEqual([label]);
    links.forEach((l) => expect(l).toHaveClass("ctl"));
  });

  it("shows the strip with a legend and a dated clock", () => {
    renderShell();
    expect(screen.getByRole("note", { name: /Legend/ })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /\d{4}.*\d{2}:\d{2}/ })).toBeInTheDocument();
  });

  it("puts Presence in the left rail with the bell and a named connection dot", () => {
    renderShell();
    const rail = screen.getByRole("complementary", { name: "Ze status" });
    expect(within(rail).getByTestId("presence")).toHaveAttribute("data-compact", "false");
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Connected" })).toBeInTheDocument();
    act(() => useWsStore.setState({ isConnected: false }));
    expect(screen.getByRole("img", { name: "Offline" })).toBeInTheDocument();
  });

  it("drives Presence from the real signals", () => {
    renderShell();
    expect(screen.getByTestId("presence")).toHaveAttribute("data-state", "idle");
    act(() => useWsStore.setState({ isConnected: false }));
    expect(screen.getByTestId("presence")).toHaveAttribute("data-state", "error");
  });

  it("renders the Ask bar on every place, /ask included", () => {
    const { unmount } = renderShell("/doing");
    expect(screen.getByRole("textbox", { name: /Ask Ze/ })).toBeInTheDocument();
    unmount();
    renderShell("/ask");
    expect(screen.getByRole("textbox", { name: /Ask Ze/ })).toBeInTheDocument();
  });

  it("sends straight to the selected thread on /ask, with the chosen context and files", () => {
    useSession.setState({ threadId: "t-ask" });
    useAskOverlay.setState({ explicitContext: { origin: "chat_about" } as never });
    renderShell("/ask");
    fireEvent.change(screen.getByRole("textbox", { name: /Ask Ze/ }), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(mocks.sendTurn).toHaveBeenCalledWith("t-ask", "hello", { explicitContext: { origin: "chat_about" }, workspacePlaced: undefined });
    expect(useAskOverlay.getState().outbox).toBeNull();
  });

  it("queues in the overlay everywhere else, with the route context", () => {
    renderShell("/doing/goals/g1");
    fireEvent.change(screen.getByRole("textbox", { name: /Ask Ze/ }), { target: { value: "why slipping?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(mocks.sendTurn).not.toHaveBeenCalled();
    expect(useAskOverlay.getState().outbox).toMatchObject({ text: "why slipping?", context: { place: "doing", route: "/doing/goals/g1" } });
  });

  it("shows the displaced line with Use here, disables the Ask bar with that reason, and clears after takeover", () => {
    useWsStore.setState({ isConnected: false, displaced: true });
    renderShell("/doing");
    expect(screen.getByText("Ze is open in another window")).toBeInTheDocument();
    expect(screen.getByTestId("presence")).toHaveAttribute("data-state", "idle");
    expect(screen.getByRole("img", { name: "Open in another window" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Ze is open in another window/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Use here" }));
    expect(mocks.takeOver).toHaveBeenCalledTimes(1);
    act(() => useWsStore.setState({ displaced: false, isConnected: true }));
    expect(screen.queryByText("Ze is open in another window")).toBeNull();
  });

  it("renders the overlay slot", () => {
    renderShell("/", <i data-testid="overlay" />);
    expect(screen.getByTestId("overlay")).toBeInTheDocument();
  });

  it("has no bottom bar", () => {
    renderShell();
    expect(screen.getAllByRole("navigation", { name: "Places" })).toHaveLength(1);
  });

  it("makes Presence glance at the bell when a notification arrives", () => {
    renderShell();
    act(() => mocks.handlers.get("notification")?.forEach((h) => h({ type: "notification" })));
    expect(mocks.glance).toHaveBeenCalledTimes(1);
    const target = mocks.glance.mock.calls[0][0] as HTMLElement;
    expect(target).toContainElement(screen.getByRole("button", { name: "Notifications" }));
  });

  it("makes Presence glance at the overlay when it opens", async () => {
    renderShell("/", <div className="ask-overlay" />);
    act(() => useAskOverlay.getState().openWith(null, null));
    await vi.waitFor(() => expect(mocks.glance).toHaveBeenCalled());
    expect((mocks.glance.mock.calls.at(-1)![0] as HTMLElement).className).toBe("ask-overlay");
  });
});

describe("AppShell phone", () => {
  beforeEach(() => mm.set("(max-width: 1023px)", true));

  it("hides the top tabs and shows five labelled bottom links", () => {
    const { container } = renderShell("/mind");
    const nav = screen.getByRole("navigation", { name: "Places" });
    expect(nav).toHaveClass("bottombar");
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("aria-label"))).toEqual(["World", "Ask", "Doing", "Mind", "Governance"]);
    links.forEach((l) => expect(l).toHaveClass("ctl"));
    expect(links.find((l) => l.getAttribute("aria-label") === "Mind")).toHaveAttribute("aria-current", "page");
    expect(container.querySelectorAll(".top .tabs")).toHaveLength(0);
  });

  it("puts the Ask bar before the bottom bar and Presence compact", () => {
    const { container } = renderShell();
    expect(screen.getByTestId("presence")).toHaveAttribute("data-compact", "true");
    const ask = container.querySelector("form.bottom")!;
    const bar = container.querySelector("nav.bottombar")!;
    expect(ask.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("navigates from the bottom bar", () => {
    renderShell("/");
    fireEvent.click(screen.getByRole("link", { name: "Doing" }));
    expect(screen.getByRole("link", { name: "Doing" })).toHaveAttribute("aria-current", "page");
  });
});

describe("AppShell voice and ambience", () => {
  it("shows the mic from VoiceMic inside the Ask bar", () => {
    renderShell("/doing");
    const mic = screen.getByRole("button", { name: "Speak to Ze (hold V)" });
    expect(mic.closest(".ask")).not.toBeNull();
    expect(mic).toHaveClass("ctl");
  });

  it("shows the ambience toggle in the Presence head", () => {
    renderShell();
    const toggle = within(screen.getByTestId("presence-head")).getByRole("button", { name: "Ambience off" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  it("renders the voice status line above the bar, outside .ask", () => {
    renderShell();
    const line = document.querySelector(".voice-status");
    expect(line).not.toBeNull();
    expect(line).toHaveAttribute("role", "status");
    expect(line!.closest(".ask")).toBeNull();
  });

  it("wires registerTranscript to the bar", async () => {
    const mod = await import("@/features/voice-input/model/store");
    renderShell("/ask");
    act(() => mod.deliverTranscript("hello", "t1"));
    expect(screen.getByRole("textbox", { name: /Ask Ze/ })).toHaveValue("hello");
    expect(useAskOverlay.getState().voiceId).toBe("t1");
  });

  it("stops a recording when the overlay closes", () => {
    const stop = vi.fn();
    useVoiceInput.setState({ status: "recording", stop });
    useAskOverlay.setState({ open: true });
    renderShell("/doing");
    expect(stop).not.toHaveBeenCalled();
    act(() => useAskOverlay.getState().close());
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it("does not stop a recording when the person changes place", () => {
    const stop = vi.fn();
    useVoiceInput.setState({ status: "recording", stop });
    const { rerender } = renderShell("/doing");
    rerender(
      <MemoryRouter initialEntries={["/mind"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="*" element={<p>page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(stop).not.toHaveBeenCalled();
  });

  it("does not stop an idle mic when the overlay closes", () => {
    const stop = vi.fn();
    useVoiceInput.setState({ status: "idle", stop });
    useAskOverlay.setState({ open: true });
    renderShell("/doing");
    act(() => useAskOverlay.getState().close());
    expect(stop).not.toHaveBeenCalled();
  });
});
