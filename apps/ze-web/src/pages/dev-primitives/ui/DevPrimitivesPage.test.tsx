import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { DevPrimitivesPage } from "./DevPrimitivesPage";

describe("DevPrimitivesPage", () => {
  it("renders one section per primitive type, each with a 390 px frame", () => {
    render(
      <MemoryRouter>
        <DevPrimitivesPage />
      </MemoryRouter>,
    );
    const sections = screen.getAllByRole("region");
    expect(sections.length).toBeGreaterThan(10);
    for (const type of ["button", "table", "claim_card"]) {
      const section = screen.getByRole("region", { name: type });
      expect(within(section).getAllByTestId("frame-390").length).toBeGreaterThan(0);
      expect(within(section).getAllByTestId("frame-natural").length).toBeGreaterThan(0);
    }
  });

  it("leaves out fixtures the client does not accept as valid", () => {
    render(
      <MemoryRouter>
        <DevPrimitivesPage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("region", { name: "unknown" })).toBeNull();
    expect(screen.queryByRole("region", { name: "missing" })).toBeNull();
    expect(screen.queryByRole("region", { name: "string" })).toBeNull();
  });

  it("shows the typed action a button runs instead of running it", () => {
    render(
      <MemoryRouter>
        <DevPrimitivesPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Ask" })[0]);
    expect(screen.getByRole("status")).toHaveTextContent('"kind":"ask"');
  });
});
