import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import button from "../../../../../../packages/ze-ui/fixtures/button.json";
import { manifestFixture } from "@/test/fixtures/manifest";
import { Connections } from "./Connections";

const m = vi.hoisted(() => ({
  saveConfig: vi.fn(),
  clearConfig: vi.fn(),
  reconnect: vi.fn(),
  resetClient: vi.fn(),
  useUiManifestQuery: vi.fn(),
  usePluginSettingsQuery: vi.fn(),
  onAction: vi.fn(),
}));

vi.mock("@/shared/config", async (orig) => ({
  ...(await orig<typeof import("@/shared/config")>()),
  getConfig: () => ({ serverUrl: "http://ze:8000", apiKey: "secret" }),
  saveConfig: m.saveConfig,
  clearConfig: m.clearConfig,
}));
vi.mock("@/shared/api", () => ({ reconnect: m.reconnect }));
vi.mock("@/shared/lib", async (orig) => ({ ...(await orig<typeof import("@/shared/lib")>()), resetClient: m.resetClient }));
vi.mock("@/entities/ui-manifest", () => ({
  useUiManifestQuery: m.useUiManifestQuery,
  usePluginSettingsQuery: m.usePluginSettingsQuery,
}));
vi.mock("@/features/choose-palette", () => ({ ChoosePalette: () => <div data-testid="palette" /> }));
vi.mock("@/features/primitive-tree", async (orig) => ({ ...(await orig<typeof import("@/features/primitive-tree")>()), usePrimitiveActions: () => ({ onAction: m.onAction }) }));

const fetchMock = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  m.useUiManifestQuery.mockReturnValue({ data: manifestFixture });
  m.usePluginSettingsQuery.mockReturnValue({ data: { tree: [], ui_version: "2.0" }, isLoading: false, isError: false, refetch: vi.fn() });
});

const view = (extra?: ReactNode) => render(<MemoryRouter><Connections extra={extra} /></MemoryRouter>);

describe("Connections", () => {
  it("saves the URL and key and reconnects", () => {
    view();
    fireEvent.change(screen.getByLabelText("Server URL"), { target: { value: "http://new:9000" } });
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "k2" } });
    fireEvent.click(screen.getByRole("button", { name: /save and reconnect/i }));
    expect(m.saveConfig).toHaveBeenCalledWith({ serverUrl: "http://new:9000", apiKey: "k2" });
    expect(m.resetClient).toHaveBeenCalled();
    expect(m.reconnect).toHaveBeenCalled();
  });

  it("reports the server version when the test succeeds", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ api_version: "0.42.0", client_version: "0.42.0" }) });
    view();
    fireEvent.click(screen.getByRole("button", { name: /^test$/i }));
    expect(await screen.findByText(/API 0\.42\.0/i)).toBeInTheDocument();
  });

  it("reports the failing reason when the test fails", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      url.endsWith("/version") ? { ok: true, status: 200, json: async () => ({ api_version: "v0" }) } : { ok: false, status: 401, json: async () => ({}) },
    );
    view();
    fireEvent.click(screen.getByRole("button", { name: /^test$/i }));
    expect(await screen.findByText(/reachable, but it rejected the api key/i)).toBeInTheDocument();
    fetchMock.mockRejectedValue(new Error("down"));
    fireEvent.click(screen.getByRole("button", { name: /^test$/i }));
    expect(await screen.findByText(/could not reach the server/i)).toBeInTheDocument();
  });

  it("renders plugin settings sections and the palette", () => {
    view();
    expect(screen.getByText("Fixture")).toBeInTheDocument();
    expect(screen.getByTestId("palette")).toBeInTheDocument();
  });

  it("renders the fixture settings section and dispatches a save as its tool action", () => {
    m.usePluginSettingsQuery.mockReturnValue({ data: { tree: button, ui_version: "2.0" }, isLoading: false, isError: false, refetch: vi.fn() });
    view();
    expect(m.usePluginSettingsQuery).toHaveBeenCalledWith(expect.objectContaining({ id: "fixture.settings", settings_operation_id: "getNewsSettings" }), true);
    fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
    expect(m.onAction).toHaveBeenCalledWith({ kind: "tool", owner: "news", tool: "mark_source_read", args: { source_id: "s-12" } });
  });

  it("renders the extra content (the module slot) after the settings sections", () => {
    view(<section aria-label="slot governance.connections" />);
    const slot = screen.getByRole("region", { name: "slot governance.connections" });
    const settings = screen.getByText("Fixture");
    expect(settings.compareDocumentPosition(slot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("forgets this server only after one confirmation", async () => {
    Object.defineProperty(window, "location", { value: { ...window.location, reload: vi.fn() }, writable: true });
    view();
    fireEvent.click(screen.getByRole("button", { name: /forget this server/i }));
    expect(m.clearConfig).not.toHaveBeenCalled();
    expect(screen.getByText(/removes the saved server url and api key/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^forget$/i }));
    await waitFor(() => expect(m.clearConfig).toHaveBeenCalledTimes(1));
  });

  it("has no Reset control", () => {
    view();
    expect(screen.queryByRole("button", { name: /reset/i })).toBeNull();
  });
});
