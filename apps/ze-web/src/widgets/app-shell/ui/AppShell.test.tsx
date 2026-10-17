import type { WsInboundFrame } from "@myguyze/ze-client";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";

const mocks = vi.hoisted(() => ({
  glance: vi.fn(),
  handlers: new Map<string, Set<(f: unknown) => void>>(),
}));

vi.mock("@/shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api")>();
  return {
    ...actual,
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
vi.mock("./NotificationBell", () => ({ NotificationBell: () => <button type="button">Notifications</button> }));
vi.mock("@/shared/ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/ui")>()),
  NoticeBanner: () => null,
  Presence: forwardRef(function PresenceStub(props: { state: string; phrase: string; compact?: boolean }, ref) {
    useImperativeHandle(ref, () => ({ glance: mocks.glance }), []);
    return (
      <section data-testid="presence" data-state={props.state} data-compact={String(!!props.compact)}>
        {props.phrase}
      </section>
    );
  }),
}));

import { useAskOverlay } from "@/features/ask-bar";
import { usePresenceStore } from "@/entities/presence";
import { useWsStore } from "@/shared/api";
import { AppShell } from "./AppShell";

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
  mm = mockMatchMedia({});
  mocks.glance.mockClear();
  mocks.handlers.clear();
  useAskOverlay.getState().reset();
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

  it("renders the Ask bar except on /ask", () => {
    const { unmount } = renderShell("/doing");
    expect(screen.getByRole("textbox", { name: /Ask Ze/ })).toBeInTheDocument();
    unmount();
    renderShell("/ask");
    expect(screen.queryByRole("textbox", { name: /Ask Ze/ })).not.toBeInTheDocument();
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
