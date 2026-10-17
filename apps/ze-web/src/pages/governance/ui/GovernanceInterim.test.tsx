import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { GovernanceInterim } from "./GovernanceInterim";

const page = (name: string) => () => Promise.resolve({ default: () => <p>{name} page</p> });
const loaders = { usage: page("usage"), data: page("data"), settings: page("settings") };

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <GovernanceInterim loaders={loaders} />
    </MemoryRouter>,
  );
}

describe("GovernanceInterim", () => {
  it("lists Usage, Data and Settings, with Usage as the index", async () => {
    at("/governance");
    const tabs = within(screen.getByRole("navigation", { name: "Governance sections" })).getAllByRole("link");
    expect(tabs.map((t) => t.textContent)).toEqual(["Usage", "Data", "Settings"]);
    expect(await screen.findByText("usage page")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Palette" })).not.toBeInTheDocument();
  });

  it("puts the palette control above Settings only", async () => {
    at("/governance/settings");
    expect(await screen.findByText("settings page")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Palette" })).toBeInTheDocument();
  });

  it("shows Data at /governance/data", async () => {
    at("/governance/data");
    expect(await screen.findByText("data page")).toBeInTheDocument();
  });
});
