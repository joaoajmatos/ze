import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { MindInterim } from "./MindInterim";

const page = (name: string) => () => Promise.resolve({ default: () => <p>{name} page</p> });
const loaders = { memory: page("memory"), graph: page("graph") };

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <MindInterim loaders={loaders} />
    </MemoryRouter>,
  );
}

describe("MindInterim", () => {
  it("lists Memory and Graph, with Memory as the index", async () => {
    at("/mind");
    const tabs = within(screen.getByRole("navigation", { name: "Mind sections" })).getAllByRole("link");
    expect(tabs.map((t) => t.textContent)).toEqual(["Memory", "Graph"]);
    expect(await screen.findByText("memory page")).toBeInTheDocument();
  });

  it("shows Graph at /mind/graph", async () => {
    at("/mind/graph");
    expect(await screen.findByText("graph page")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Graph" })).toHaveAttribute("aria-current", "page");
  });
});
