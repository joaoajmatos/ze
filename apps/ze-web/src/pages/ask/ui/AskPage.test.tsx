import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/match-media";

const m = vi.hoisted(() => ({ sendTurn: vi.fn(() => true) }));
vi.mock("@/features/turn-stream", () => ({ sendTurn: m.sendTurn }));
vi.mock("@/widgets/assemble", () => ({
  Canvas: ({ threadId, onSelect }: { threadId: string; onSelect?: (id: string) => void }) => (
    <div data-testid="canvas">
      {threadId}
      <button type="button" onClick={() => onSelect?.("m1")}>
        trace this reply
      </button>
    </div>
  ),
  ConfirmationPlacement: () => null,
  RetryControl: () => <div data-testid="retry" />,
  TraceModule: ({ messageId }: { messageId: string | null }) => <div data-testid="trace">{messageId ?? "latest"}</div>,
  TraceSheet: () => <div data-testid="sheet" />,
}));
vi.mock("@/widgets/sessions-rail", () => ({ SessionsRail: () => <div data-testid="rail" /> }));
vi.mock("@/widgets/try-chips", () => ({
  TryChips: ({ onSend }: { onSend: (t: string, c: object) => boolean }) => (
    <button type="button" onClick={() => onSend("What's slipping?", { compose: "slipping", origin: "preset" })}>
      try
    </button>
  ),
}));
vi.mock("@/entities/conversation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/conversation")>()),
  useThreadHistory: () => ({ loadHistory: vi.fn(), reload: vi.fn() }),
}));

import { useAskOverlay } from "@/features/ask-bar";
import { emptyThread, useConversation } from "@/entities/conversation";
import { useOnboardingSession } from "@/entities/onboarding-session";
import { useSession } from "@/entities/session";
import { useWsStore } from "@/shared/api";
import { useRailSlot } from "@/shared/lib";
import { AskPage } from "./AskPage";

let mm: ReturnType<typeof mockMatchMedia>;
const mount = (at = "/ask") =>
  render(
    <MemoryRouter initialEntries={[at]}>
      <Routes>
        <Route path="/ask" element={<AskPage />} />
        <Route path="/ask/:threadId" element={<AskPage />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  mm = mockMatchMedia({ "(max-width: 1023px)": false });
  localStorage.clear();
  m.sendTurn.mockClear();
  useSession.setState({ threadId: "t1" });
  useConversation.setState({ byThread: { t1: { ...emptyThread(), historyLoaded: true } } });
  useOnboardingSession.getState().clear();
  useAskOverlay.getState().reset();
  useWsStore.setState({ isConnected: true, displaced: false });
});
afterEach(() => mm.restore());

describe("AskPage", () => {
  it("lays out the rail, the canvas and the trace on a desktop", () => {
    mount();
    expect(screen.getByTestId("rail")).toBeInTheDocument();
    expect(screen.getByTestId("canvas")).toHaveTextContent("t1");
    expect(screen.getByTestId("trace")).toBeInTheDocument();
  });

  it("renders the rail inline when the shell has no rail slot", () => {
    useRailSlot.setState({ element: null });
    const { container } = mount();
    expect(container.querySelector(".ask-page .ask-rail")).not.toBeNull();
  });

  it("portals the rail into the shell rail slot, outside the page", () => {
    const slot = document.createElement("div");
    document.body.appendChild(slot);
    useRailSlot.setState({ element: slot });
    const { container } = mount();
    expect(slot.querySelector(".ask-rail")).not.toBeNull();
    expect(container.querySelector(".ask-page .ask-rail")).toBeNull();
    useRailSlot.setState({ element: null });
    slot.remove();
  });

  it("orders a phone as try, sessions, canvas, then a Trace control that opens the sheet", () => {
    mm.set("(max-width: 1023px)", true);
    mount();
    expect(screen.queryByTestId("trace")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Open the trace of the selected reply" }));
    expect(screen.getByTestId("sheet")).toBeInTheDocument();
  });

  it("fills the trace rail when a reply is selected on a desktop", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "trace this reply" }));
    expect(screen.getByTestId("trace")).toHaveTextContent("m1");
  });

  it("opens the trace sheet when a reply is selected on a phone", () => {
    mm.set("(max-width: 1023px)", true);
    mount();
    expect(screen.queryByTestId("sheet")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "trace this reply" }));
    expect(screen.getByTestId("sheet")).toBeInTheDocument();
  });

  it("selects the thread the URL names", () => {
    mount("/ask/t9");
    expect(useSession.getState().threadId).toBe("t9");
  });

  it("sends a preset on the selected thread", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "try" }));
    expect(m.sendTurn).toHaveBeenCalledWith("t1", "What's slipping?", { explicitContext: { compose: "slipping", origin: "preset" } });
  });

  it("opens the onboarding thread once per session id, not again after a reconnect re-send", () => {
    mount();
    act(() => useOnboardingSession.getState().setSession("s1", false));
    expect(useSession.getState().threadId).toBe("onboarding:s1");
    act(() => useSession.getState().selectSession("t1"));
    act(() => useOnboardingSession.getState().setSession("s1", false));
    expect(useSession.getState().threadId).toBe("t1");
    expect(screen.getByRole("button", { name: /Continue getting to know you/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Continue getting to know you/ }));
    expect(useSession.getState().threadId).toBe("onboarding:s1");
  });

  it("never jumps to onboarding when the URL names a thread or the bar has text", () => {
    useAskOverlay.setState({ draft: "typing" });
    mount();
    act(() => useOnboardingSession.getState().setSession("s2", false));
    expect(useSession.getState().threadId).toBe("t1");
    expect(screen.getByRole("button", { name: /Continue getting to know you/ })).toBeInTheDocument();
  });
});
