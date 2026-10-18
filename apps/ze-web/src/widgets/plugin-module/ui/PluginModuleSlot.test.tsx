import { act, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ModuleSubject } from "@/entities/ui-manifest";
import { manifestFixture } from "@/test/fixtures/manifest";
import { PluginModuleSlot } from "./PluginModuleSlot";

const m = vi.hoisted(() => ({
  manifest: undefined as unknown,
  results: {} as Record<string, unknown>,
  useUiModuleQuery: vi.fn(),
}));

vi.mock("@/entities/ui-manifest", async (orig) => ({
  ...(await orig<typeof import("@/entities/ui-manifest")>()),
  useUiManifestQuery: () => ({ data: m.manifest }),
  useUiModuleQuery: m.useUiModuleQuery,
}));

const actionsSpy = vi.hoisted(() => vi.fn(() => ({ tag: "actions" })));
vi.mock("@/features/primitive-tree/api/usePrimitiveActions", () => ({ usePrimitiveActions: actionsSpy }));

type Observer = { cb: IntersectionObserverCallback; el: Element };
let observers: Observer[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  observers = [];
  m.manifest = manifestFixture;
  m.results = {};
  m.useUiModuleQuery.mockImplementation((id: string) => m.results[id] ?? { data: undefined, isLoading: true, isError: false });
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(private cb: IntersectionObserverCallback) {}
      observe(el: Element) {
        observers.push({ cb: this.cb, el });
      }
      unobserve() {}
      disconnect() {}
    },
  );
});

const view = (slot: "mind.entity" = "mind.entity") =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PluginModuleSlot slot={slot} subject={subject} />
      </MemoryRouter>
    </QueryClientProvider>,
  );

const subject: ModuleSubject = { kind: "entity", id: "e1" };
const ok = (id: string, text = "Hello from plugin") => ({
  data: { module_id: id, applies: true, ui_version: "2.0", components: [{ type: "text", content: text }] },
  isLoading: false,
  isError: false,
});

const setVisible = (visible: boolean) =>
  act(() => observers.forEach((o) => o.cb([{ isIntersecting: visible, target: o.el } as IntersectionObserverEntry], {} as IntersectionObserver)));

describe("PluginModuleSlot", () => {
  it("renders nothing for a slot with no modules", () => {
    m.manifest = { modules: [], presets: [], settings_sections: [] };
    const { container } = view();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders each module in a Module titled with its label, in priority order", () => {
    m.manifest = {
      ...manifestFixture,
      modules: [
        { ...manifestFixture.modules[0], id: "a.first", label: "Alpha" },
        { ...manifestFixture.modules[0], id: "b.second", label: "Beta" },
        manifestFixture.modules[1],
      ],
    };
    m.results = { "a.first": ok("a.first", "one"), "b.second": ok("b.second", "two") };
    view();
    const headings = screen.getAllByRole("heading").map((h) => h.textContent);
    expect(headings).toEqual(["Alpha", "Beta"]);
    expect(screen.getByText("one")).toBeInTheDocument();
    expect(screen.getByText("two")).toBeInTheDocument();
  });

  it("shows a loading line while waiting", () => {
    view();
    expect(screen.getByText("Loading Fixture facet…")).toBeInTheDocument();
  });

  it("shows the server's detail on error and still renders the other modules", () => {
    m.manifest = {
      ...manifestFixture,
      modules: [
        { ...manifestFixture.modules[0], id: "a.bad", label: "Bad" },
        { ...manifestFixture.modules[0], id: "b.good", label: "Good" },
      ],
    };
    m.results = {
      "a.bad": { data: undefined, isLoading: false, isError: true, error: new Error("News could not load.") },
      "b.good": ok("b.good", "still here"),
    };
    view();
    expect(screen.getByText("News could not load.")).toBeInTheDocument();
    expect(screen.getByText("still here")).toBeInTheDocument();
  });

  it("renders nothing for a module that does not apply", () => {
    m.results = {
      "fixture.entity": { data: { module_id: "fixture.entity", applies: false, components: [], ui_version: "2.0" }, isLoading: false, isError: false },
    };
    const { container } = view();
    expect(screen.queryByRole("heading")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("polls every 60 s while visible and not when off screen", () => {
    m.results = { "fixture.entity": ok("fixture.entity") };
    view();
    const last = () => m.useUiModuleQuery.mock.calls.at(-1);
    expect(last()?.[2]).toEqual({ refetchInterval: false });
    setVisible(true);
    expect(last()?.[0]).toBe("fixture.entity");
    expect(last()?.[1]).toEqual(subject);
    expect(last()?.[2]).toEqual({ refetchInterval: 60_000 });
    setVisible(false);
    expect(last()?.[2]).toEqual({ refetchInterval: false });
  });

  it("wires module actions through usePrimitiveActions", () => {
    m.results = { "fixture.entity": ok("fixture.entity") };
    view();
    expect(actionsSpy).toHaveBeenCalled();
  });

  it("shows the primitive fallback for an unknown primitive", () => {
    m.results = {
      "fixture.entity": {
        data: { module_id: "fixture.entity", applies: true, ui_version: "2.0", components: [{ type: "no_such_primitive_xyz" }] },
        isLoading: false,
        isError: false,
      },
    };
    view();
    expect(screen.getByRole("heading", { name: "Fixture facet" })).toBeInTheDocument();
    expect(screen.queryByText(/could not load/i)).toBeNull();
  });
});
