import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { WorldInterim } from "./WorldInterim";

const page = (name: string) => () => Promise.resolve({ default: () => <p>{name} page</p> });
const loaders = { loops: page("loops"), priority: page("priority") };

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <WorldInterim loaders={loaders} />
    </MemoryRouter>,
  );
}

describe("WorldInterim", () => {
  it("lists Open loops and Priority, with Open loops as the index", async () => {
    at("/");
    const tabs = within(screen.getByRole("navigation", { name: "World sections" })).getAllByRole("link");
    expect(tabs.map((t) => t.textContent)).toEqual(["Open loops", "Priority"]);
    expect(await screen.findByText("loops page")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open loops" })).toHaveAttribute("aria-current", "page");
  });

  it("shows Priority at /world/priority", async () => {
    at("/world/priority");
    expect(await screen.findByText("priority page")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Priority" })).toHaveAttribute("aria-current", "page");
  });
});
