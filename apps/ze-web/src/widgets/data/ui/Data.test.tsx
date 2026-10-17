import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Data } from "./Data";

const m = vi.hoisted(() => ({
  useDataDomainsQuery: vi.fn(),
  downloadExport: vi.fn(),
  importArchive: vi.fn(),
  createDeleteIntent: vi.fn(),
  deleteData: vi.fn(),
}));

vi.mock("@/entities/data-domain", () => ({ useDataDomainsQuery: m.useDataDomainsQuery }));
vi.mock("@/shared/config", async (orig) => ({
  ...(await orig<typeof import("@/shared/config")>()),
  getConfig: () => ({ serverUrl: "http://ze", apiKey: "k" }),
  clearConfig: vi.fn(),
}));
vi.mock("@myguyze/ze-client", async (orig) => ({
  ...(await orig<typeof import("@myguyze/ze-client")>()),
  downloadExport: m.downloadExport,
  importArchive: m.importArchive,
  createDeleteIntent: m.createDeleteIntent,
  deleteData: m.deleteData,
}));

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(window, "location", { value: { ...window.location, reload: vi.fn() }, writable: true });
  m.useDataDomainsQuery.mockReturnValue({
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    data: {
      domains: [
        { name: "memory.facts", importable: true, count: 1200, size_bytes: 40960 },
        { name: "acme.widget_orders", importable: false, count: null, size_bytes: 0 },
      ],
      schema_revisions: [],
      total_records: 1200,
      total_size_bytes: 40960,
    },
  });
});

describe("Data", () => {
  it("shows domains with plain labels and counts, no table names or IMPORTABLE badge", () => {
    render(<MemoryRouter><Data /></MemoryRouter>);
    expect(screen.getByText("Facts")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
    expect(screen.getByText("Widget orders")).toBeInTheDocument();
    expect(screen.queryByText(/memory\.facts/)).toBeNull();
    expect(screen.queryByText(/importable/i)).toBeNull();
  });

  it("shows preparing while the export runs, then done", async () => {
    let finish!: () => void;
    m.downloadExport.mockReturnValue(new Promise<void>((r) => (finish = r)));
    render(<MemoryRouter><Data /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    expect(await screen.findByText(/preparing/i)).toBeInTheDocument();
    finish();
    await waitFor(() => expect(screen.queryByText(/preparing/i)).toBeNull());
  });

  it("imports a .zip and reports the result", async () => {
    m.importArchive.mockResolvedValue({ domains_imported: ["a", "b"], rows_imported: { a: 3, b: 4 } });
    const { container } = render(<MemoryRouter><Data /></MemoryRouter>);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toHaveAttribute("accept", ".zip");
    fireEvent.change(input, { target: { files: [new File(["x"], "ze.zip")] } });
    expect(await screen.findByText(/imported 2 domains \(7 rows\)/i)).toBeInTheDocument();
  });

  it("deletes only after the typed DELETE confirmation, through the intent step", async () => {
    m.createDeleteIntent.mockResolvedValue({ data: { confirmation_token: "tok" } });
    m.deleteData.mockResolvedValue({});
    render(<MemoryRouter><Data /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /delete all data/i }));
    const confirm = screen.getByRole("button", { name: /delete everything/i });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("DELETE"), { target: { value: "DELETE" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(m.deleteData).toHaveBeenCalledWith({ body: { confirmation_token: "tok" } }));
    expect(m.createDeleteIntent).toHaveBeenCalledBefore(m.deleteData);
  });

  it("names a failed read", () => {
    m.useDataDomainsQuery.mockReturnValue({ isLoading: false, isError: true, refetch: vi.fn(), data: undefined });
    render(<MemoryRouter><Data /></MemoryRouter>);
    expect(screen.getByText(/could not load your data/i)).toBeInTheDocument();
  });
});
