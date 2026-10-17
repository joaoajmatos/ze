import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { DoingInterim } from "./DoingInterim";

const page = (name: string) => () => Promise.resolve({ default: () => <p>{name} page</p> });
const loaders = { goals: page("goals"), workflows: page("workflows"), skills: page("skills") };

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DoingInterim loaders={loaders} fallback={<p>nothing here</p>} />
    </MemoryRouter>,
  );
}

describe("DoingInterim", () => {
  it("lists the four sections", () => {
    at("/doing");
    const tabs = within(screen.getByRole("navigation", { name: "Doing sections" })).getAllByRole("link");
    expect(tabs.map((t) => t.textContent)).toEqual(["Goals", "Workflows", "Skills"]);
  });

  it("makes Goals the index", async () => {
    at("/doing");
    expect(await screen.findByText("goals page")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Goals" })).toHaveAttribute("aria-current", "page");
  });

  it.each([
    ["/doing/workflows", "Workflows", "workflows page"],
    ["/doing/skills", "Skills", "skills page"],
  ])("%s follows the URL", async (path, label, content) => {
    at(path);
    expect(await screen.findByText(content)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: label })).toHaveAttribute("aria-current", "page");
  });

  it("leaves an unowned path to the fallback", () => {
    at("/doing/nope");
    expect(screen.getByText("nothing here")).toBeInTheDocument();
  });
});
