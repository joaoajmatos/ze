import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAskOverlay } from "@/features/ask-bar";
import { usePresenceStore } from "@/entities/presence";
import { useScreenContextStore } from "@/entities/screen-context";
import type { Concern } from "@/shared/lib";
import { useRailSlot } from "@/shared/lib";
import { concern, day, NOW } from "@/widgets/world-field/lib/fixtures";
import type { WorldModel } from "../model/useWorld";
import { WorldPage } from "./WorldPage";

const m = vi.hoisted(() => ({ world: null as unknown, connected: true, narrow: false, reduced: false }));

vi.mock("../model/useWorld", () => ({ useWorld: () => m.world }));
vi.mock("@/shared/api", () => ({
  send: vi.fn(() => true),
  useFrame: () => {},
  useWsStore: (sel: (s: { isConnected: boolean; setThreadThinking: () => void }) => unknown) => sel({ isConnected: m.connected, setThreadThinking: () => {} }),
}));
vi.mock("@/entities/session", () => ({ useSession: (sel: (s: { threadId: string }) => unknown) => sel({ threadId: "t-1" }) }));
vi.mock("@/shared/lib", async (orig) => ({
  ...(await orig<typeof import("@/shared/lib")>()),
  useNarrow: () => m.narrow,
  useReducedMotion: () => m.reduced,
}));

function model(over: Partial<WorldModel> = {}, concerns: Concern[] = []): WorldModel {
  const part = <T,>(data: T) => ({ data, loading: false, error: false });
  const slipped = concerns.filter((c) => c.slipped).length;
  return {
    loading: false,
    now: NOW,
    since: day(-1),
    sourcesFailed: [],
    field: part(concerns),
    recordsFailed: [],
    decisions: part([]),
    loops: part([]),
    doing: part({ goals: [], workflows: [], executions: {} }),
    touched: part({ closedLoops: [], loops: [], goals: [], workflows: [] }),
    away: part({ notifications: [], jobRuns: [], budget: null }),
    counts: { slipped, watched: concerns.length, waiting: 0 },
    sentence: "One promise slipped. I am watching one concern.",
    running: false,
    failedRun: false,
    ...over,
  } as WorldModel;
}

function renderPage(url = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <WorldPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const slippedLoop = concern("ana", { title: "Reply to Ana", state: "drifting", slipped: true, due: day(-3), confidence: 0.62, rank: 1 });
function FocusLink() {
  const navigate = useNavigate();
  return (
    <button type="button" data-testid="go-bo" onClick={() => navigate("/?focus=loop:bo")}>
      go
    </button>
  );
}

const signal = () => usePresenceStore.getState().presence.worldSignal;

describe("WorldPage", () => {
  beforeEach(() => {
    m.connected = true;
    m.narrow = false;
    m.reduced = false;
    m.world = model({}, [slippedLoop]);
    useRailSlot.setState({ element: null });
    useScreenContextStore.getState().reset();
    useAskOverlay.getState().reset();
    usePresenceStore.getState().reset();
  });

  it("lays out the sentence, the field, the rails and the decisions", () => {
    renderPage();
    expect(screen.getByText("One promise slipped. I am watching one concern.")).toBeTruthy();
    for (const name of ["Needs you", "Doing now", "Loops · confidence", "Touched · 7 d", "While you were away"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: /Reply to Ana, drifting, slipped 3 days ago/ })).toBeTruthy();
  });

  it("puts Needs you and Doing now in the shell's rail slot when there is one", () => {
    const slot = document.createElement("div");
    document.body.appendChild(slot);
    useRailSlot.setState({ element: slot });
    renderPage();
    expect(slot.textContent).toContain("Needs you");
    expect(slot.textContent).toContain("Doing now");
    slot.remove();
  });

  it("phone: the field is the ranked list, not the plot", () => {
    m.narrow = true;
    const { container } = renderPage();
    expect(container.querySelector(".field-plot")).toBeNull();
    expect(container.querySelector(".field-list")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Slipped · 1" })).toBeTruthy();
  });

  it("names the sources that are down, and only then", () => {
    m.world = model({ sourcesFailed: ["hypothesis"] }, [slippedLoop]);
    const { unmount } = renderPage();
    expect(screen.getByText("1 source down: hypothesis")).toBeTruthy();
    unmount();
    m.world = model({}, [slippedLoop]);
    renderPage();
    expect(screen.queryByText(/sources? down/)).toBeNull();
  });

  it("only the field shows the error state for a failed priority source", () => {
    const base = model({}, []);
    m.world = { ...base, field: { data: [], loading: false, error: true } };
    renderPage();
    expect(screen.getByText("Couldn't read the world-state. It will try again.")).toBeTruthy();
    expect(screen.getByText("Nothing waiting on you.")).toBeTruthy();
    expect(screen.queryByText(/Nothing tracked yet/)).toBeNull();
  });

  it("loading frames show no numbers", () => {
    m.world = model({ loading: true, field: { data: [slippedLoop], loading: true, error: false } }, [slippedLoop]);
    const { container } = renderPage();
    expect(screen.getByText("Reading the world-state…", { selector: ".sentence" })).toBeTruthy();
    expect(container.querySelectorAll(".pt")).toHaveLength(0);
  });

  it("says the field is empty in words", () => {
    m.world = model({}, []);
    renderPage();
    expect(screen.getByText("Nothing tracked yet. Tell me what you are working on.")).toBeTruthy();
  });

  it("offline: says so and disables writes", () => {
    m.connected = false;
    renderPage();
    expect(screen.getByText("Ze is offline")).toBeTruthy();
    expect((screen.getByRole("button", { name: /What's slipping\?/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("What's slipping? sends the preset through the Ask overlay's one send path", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /What's slipping\?/ }));
    const s = useAskOverlay.getState();
    expect(s.open).toBe(true);
    expect(s.outbox).toMatchObject({ text: "What's slipping?", context: { place: "world", origin: "preset", compose: "slipping" } });
  });

  it("?focus=loop:<id> selects that mark", () => {
    const { container } = renderPage("/?focus=loop:ana");
    expect(container.querySelector('[data-key="loop:ana"]')!.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("region", { name: /Readout: Reply to Ana/ })).toBeTruthy();
  });

  it("a new ?focus= link selects its item even after Escape", () => {
    const other = concern("bo", { title: "Call Bo", due: day(2), confidence: 0.8, rank: 2 });
    m.world = model({}, [slippedLoop, other]);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/?focus=loop:ana"]}>
          <WorldPage />
          <FocusLink />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("region", { name: /Readout/ })).toBeNull();
    fireEvent.click(screen.getByTestId("go-bo"));
    expect(screen.getByRole("region", { name: /Readout: Call Bo/ })).toBeTruthy();
  });

  it("the preset carries the route and the screen snapshot", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /What's slipping\?/ }));
    expect(useAskOverlay.getState().outbox?.context).toMatchObject({ route: "/", captured_at: expect.any(String), origin: "preset", compose: "slipping" });
  });

  it("Escape clears the selection", () => {
    renderPage("/?focus=loop:ana");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("region", { name: /Readout/ })).toBeNull();
  });

  describe("presence signal", () => {
    it("is attention with a slipped concern", () => {
      renderPage();
      expect(signal()).toBe("attention");
    });
    it("is acting with a running execution and nothing slipped", () => {
      m.world = model({ running: true }, [concern("calm", { due: day(3) })]);
      renderPage();
      expect(signal()).toBe("acting");
    });
    it("attention wins over acting, a failed run is attention, and calm is null", () => {
      m.world = model({ running: true, failedRun: true }, []);
      const { unmount } = renderPage();
      expect(signal()).toBe("attention");
      unmount();
      m.world = model({}, [concern("calm", { due: day(3) })]);
      renderPage();
      expect(signal()).toBeNull();
    });
    it("clears on unmount", () => {
      const { unmount } = renderPage();
      expect(signal()).toBe("attention");
      unmount();
      expect(signal()).toBeNull();
    });
  });

  describe("leader line", () => {
    const leaders = () => document.querySelectorAll("svg.leader");
    it("renders on desktop with a slipped mark", () => {
      renderPage();
      expect(leaders()).toHaveLength(1);
    });
    it("not on phone, not under reduced motion, not without a slipped mark", () => {
      m.narrow = true;
      const a = renderPage();
      expect(leaders()).toHaveLength(0);
      a.unmount();
      m.narrow = false;
      m.reduced = true;
      const b = renderPage();
      expect(leaders()).toHaveLength(0);
      b.unmount();
      m.reduced = false;
      m.world = model({}, [concern("calm", { due: day(3) })]);
      renderPage();
      expect(leaders()).toHaveLength(0);
    });
  });

  describe("screen context", () => {
    const snapshot = async () => (await import("@/entities/screen-context")).screenSnapshot("/");
    it("publishes the focused module, the selection, and the visible rows", async () => {
      renderPage("/?focus=loop:ana");
      await act(async () => {});
      const ctx = await snapshot();
      expect(ctx.place).toBe("world");
      expect(ctx.focused_module).toBe("world-field");
      expect(ctx.selection).toEqual([{ kind: "loop", id: "ana" }]);
      expect(ctx.subject?.[0]).toMatchObject({ kind: "loop", id: "ana", label: "Reply to Ana" });
      expect(ctx.visible?.some((r) => r.kind === "loop" && r.id === "ana")).toBe(true);
    });
    it("follows focus between modules", async () => {
      renderPage();
      const needs = screen.getByRole("heading", { name: "Needs you" }).closest(".mod") as HTMLElement;
      const target = document.createElement("button");
      needs.appendChild(target);
      await act(async () => target.focus());
      const ctx = await snapshot();
      expect(ctx.focused_module).toBe("needs-you");
    });
  });
});
