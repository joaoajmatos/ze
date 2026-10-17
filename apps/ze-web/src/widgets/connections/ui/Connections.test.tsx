import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Connections } from "./Connections";

const m = vi.hoisted(() => ({
  saveConfig: vi.fn(),
  clearConfig: vi.fn(),
  reconnect: vi.fn(),
  resetClient: vi.fn(),
  useUiManifestQuery: vi.fn(),
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
  usePluginSettingsQuery: () => ({ data: { tree: [] }, isLoading: false, isError: false, refetch: vi.fn() }),
}));
vi.mock("@/features/choose-palette", () => ({ ChoosePalette: () => <div data-testid="palette" /> }));
vi.mock("@/features/primitive-tree", () => ({ usePluginScreenActions: () => ({}) }));

const fetchMock = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  m.useUiManifestQuery.mockReturnValue({ data: { settings_sections: [{ id: "news", label: "News", icon: "newspaper", path: "/x" }] } });
});

const view = () => render(<MemoryRouter><Connections /></MemoryRouter>);

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
    expect(screen.getByText("News")).toBeInTheDocument();
    expect(screen.getByTestId("palette")).toBeInTheDocument();
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
