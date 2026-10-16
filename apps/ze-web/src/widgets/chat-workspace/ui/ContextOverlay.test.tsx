import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useOverlayStore } from "@/features/open-context-overlay";
import { ContextOverlay } from "./ContextOverlay";

const chatMock = vi.hoisted(() => ({ context: undefined as unknown }));

vi.mock("../model/useChatWorkspace", () => ({
  useChatWorkspace: (options: { context?: unknown }) => {
    chatMock.context = options.context;
    return {
      messages: [],
      showTyping: false,
      typingText: null,
      streamingText: null,
      isThinking: false,
      deliveryFailed: false,
      retry: vi.fn(),
      sendMessage: vi.fn(),
    };
  },
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ContextOverlay />
    </MemoryRouter>,
  );
}

function openOverlay(patch: Partial<ReturnType<typeof useOverlayStore.getState>> = {}) {
  act(() => useOverlayStore.setState({ open: true, ...patch }));
}

describe("ContextOverlay", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    );
    Element.prototype.scrollIntoView = vi.fn();
    useOverlayStore.setState({
      open: false,
      screen: "chat",
      entityId: undefined,
      overridePath: undefined,
    });
  });

  afterEach(() => vi.unstubAllGlobals());

  describe("panel label", () => {
    it.each([
      ["/brain-memory", "Ze · Memory"],
      ["/data", "Ze · Data"],
      ["/settings", "Ze · Settings"],
      ["/goals", "Ze · Goals"],
      ["/goals/abc", "Ze · Goals"],
    ])("derives the label from the route %s", async (path, label) => {
      renderAt(path);
      openOverlay();
      expect(await screen.findByText(label)).toBeInTheDocument();
    });

    it("gives the same label whichever way the panel opens", async () => {
      renderAt("/data");
      act(() => useOverlayStore.getState().toggle());
      expect(await screen.findByText("Ze · Data")).toBeInTheDocument();
      act(() => useOverlayStore.getState().close());
      await waitFor(() => expect(screen.queryByText("Ze · Data")).not.toBeInTheDocument());
      act(() => useOverlayStore.getState().openFor("chat"));
      expect(await screen.findByText("Ze · Data")).toBeInTheDocument();
    });

    it("lets an entity-scoped screen registered for this route win", async () => {
      renderAt("/goals/abc");
      openOverlay({ screen: "goal: Learn Rust", entityId: "abc", overridePath: "/goals/abc" });
      expect(await screen.findByText("Ze · Goal: Learn Rust")).toBeInTheDocument();
      expect(chatMock.context).toEqual({ screen: "goal: Learn Rust", goal_id: "abc" });
    });

    it("ignores an entity override left over from another route", async () => {
      renderAt("/data");
      openOverlay({ screen: "goal: Learn Rust", entityId: "abc", overridePath: "/goals/abc" });
      expect(await screen.findByText("Ze · Data")).toBeInTheDocument();
      expect(chatMock.context).toEqual({ screen: "data" });
    });

    it("sends the route id as chat context", () => {
      renderAt("/brain-memory");
      openOverlay();
      expect(chatMock.context).toEqual({ screen: "brain-memory" });
    });
  });

  describe("desktop close control", () => {
    it("is a labelled Close button that dismisses the panel", async () => {
      renderAt("/data");
      openOverlay();

      const close = await screen.findByRole("button", { name: "Close" });
      expect(screen.queryByRole("button", { name: "Collapse" })).not.toBeInTheDocument();
      fireEvent.click(close);
      expect(useOverlayStore.getState().open).toBe(false);
    });
  });
});
