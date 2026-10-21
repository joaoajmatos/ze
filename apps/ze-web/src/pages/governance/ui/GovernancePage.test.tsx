import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { screenSnapshot, useScreenContextStore } from "@/entities/screen-context";
import { GovernancePage } from "./GovernancePage";

vi.mock("@/widgets/spend", () => ({ Spend: () => <section aria-label="spend-stub"><button>in spend</button></section> }));
vi.mock("@/widgets/attention", () => ({ Attention: () => <section aria-label="attention-stub"><button>in attention</button></section> }));
vi.mock("@/widgets/data", () => ({ Data: () => <div id="data" aria-label="data-stub" /> }));
vi.mock("@/widgets/connections", () => ({
  Connections: ({ extra }: { extra?: React.ReactNode }) => (
    <div id="connections" aria-label="connections-stub">
      {extra}
    </div>
  ),
}));
vi.mock("@/widgets/plugin-module", () => ({
  PluginModuleSlot: (props: { slot: string; subject: { kind: string } }) => <section aria-label={`slot ${props.slot}`} data-subject={props.subject.kind} />,
}));
vi.mock("@/widgets/files", () => ({ Files: () => <div id="files" aria-label="files-stub" /> }));

it("mounts the governance.connections slot with no subject inside Connections", () => {
  view();
  const slot = screen.getByRole("region", { name: "slot governance.connections" });
  expect(slot).toHaveAttribute("data-subject", "none");
  expect(screen.getByLabelText("connections-stub")).toContainElement(slot);
});

afterEach(() => useScreenContextStore.getState().reset());

const view = () => render(<MemoryRouter initialEntries={["/governance"]}><GovernancePage /></MemoryRouter>);

describe("GovernancePage", () => {
  it("orders modules for the phone: Attention, Spend, Connections, Data, Files", () => {
    const { container } = view();
    const order = [...container.querySelectorAll("[data-module]")].map((el) => el.getAttribute("data-module"));
    expect(order).toEqual(["Attention", "Spend", "Connections", "Data", "Files"]);
  });

  it("keeps the redirect hint targets", () => {
    view();
    for (const id of ["data", "connections", "files"]) expect(document.getElementById(id)).not.toBeNull();
  });

  it("has no Reset module", () => {
    view();
    expect(screen.queryByText(/reset/i)).toBeNull();
  });

  it("publishes the focused module for screen context, with no per-row refs", () => {
    view();
    fireEvent.focus(screen.getByRole("button", { name: "in spend" }));
    const ctx = screenSnapshot("/governance");
    expect(ctx.place).toBe("governance");
    expect(ctx.focused_module).toBe("Spend");
    expect(ctx.subject).toBeUndefined();
    expect(ctx.visible).toBeUndefined();
    fireEvent.focus(screen.getByRole("button", { name: "in attention" }));
    expect(screenSnapshot("/governance").focused_module).toBe("Attention");
  });
});
