import { fireEvent, render, screen, within } from "@testing-library/react";
import { Target } from "lucide-react";
import { MemoryRouter, NavLink } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NavGroup } from "./NavGroup";

function stubViewport(wide: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: wide,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderGroup(path = "/", props: Partial<React.ComponentProps<typeof NavGroup>> = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <NavGroup icon={Target} label="Automation" childPaths={["goals", "workflows"]} {...props}>
        <NavLink to="/goals">Goals</NavLink>
        <NavLink to="/workflows">Workflows</NavLink>
      </NavGroup>
      <button>outside</button>
    </MemoryRouter>,
  );
}

describe("NavGroup at md width", () => {
  beforeEach(() => stubViewport(false));
  afterEach(() => vi.unstubAllGlobals());

  it("names the icon-only group button after its label", () => {
    renderGroup();
    const button = screen.getByRole("button", { name: "Automation" });
    expect(button).toHaveAttribute("title", "Automation");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Goals" })).not.toBeInTheDocument();
  });

  it("opens a flyout listing every child on click", () => {
    renderGroup();
    fireEvent.click(screen.getByRole("button", { name: "Automation" }));

    const flyout = screen.getByRole("group", { name: "Automation" });
    expect(within(flyout).getByRole("link", { name: "Goals" })).toBeInTheDocument();
    expect(within(flyout).getByRole("link", { name: "Workflows" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Automation" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("closes on Escape, outside click and child selection", () => {
    renderGroup();
    const open = () => fireEvent.click(screen.getByRole("button", { name: "Automation" }));

    open();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("group", { name: "Automation" })).not.toBeInTheDocument();

    open();
    fireEvent.pointerDown(screen.getByRole("button", { name: "outside" }));
    expect(screen.queryByRole("group", { name: "Automation" })).not.toBeInTheDocument();

    open();
    fireEvent.click(screen.getByRole("link", { name: "Goals" }));
    expect(screen.queryByRole("group", { name: "Automation" })).not.toBeInTheDocument();
  });

  it("marks the group active when a child route is current", () => {
    renderGroup("/workflows/abc");
    expect(screen.getByRole("button", { name: "Automation" }).className).toContain(
      "bg-plum-voltage/15",
    );
  });

  it("leaves the group inactive on an unrelated route", () => {
    renderGroup("/settings");
    expect(screen.getByRole("button", { name: "Automation" }).className).not.toContain(
      "bg-plum-voltage/15",
    );
  });

  it("offers the group's own page first when the group has an href", () => {
    renderGroup("/goals", { href: "/", hrefIndex: true, label: "Chat" });
    fireEvent.click(screen.getByRole("button", { name: "Chat" }));

    const flyout = screen.getByRole("group", { name: "Chat" });
    expect(within(flyout).getAllByRole("link")[0]).toHaveAttribute("href", "/");
  });
});

describe("NavGroup at lg width", () => {
  beforeEach(() => stubViewport(true));
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the inline accordion with a visible label", () => {
    renderGroup("/goals");
    expect(screen.getByRole("link", { name: "Goals" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Automation" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Automation" })).toHaveTextContent("Automation");
  });
});
