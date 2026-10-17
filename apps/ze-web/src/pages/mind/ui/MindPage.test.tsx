import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { MindPage } from "./MindPage";

vi.mock("@/widgets/beliefs-feed", () => ({ BeliefsFeed: () => <section aria-label="Beliefs" /> }));
vi.mock("@/widgets/people", () => ({ People: () => <section aria-label="People" /> }));
vi.mock("@/widgets/procedures", () => ({ Procedures: () => <section aria-label="Procedures" /> }));
vi.mock("@/widgets/entity-search", () => ({
  EntitySearch: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <section aria-label="Find an entity">
      <button type="button" onClick={() => onSelect("11111111-1111-4111-8111-111111111111")}>pick</button>
    </section>
  ),
}));
vi.mock("@/features/ask-bar", () => ({ useChatAbout: () => vi.fn() }));
vi.mock("@/entities/screen-context", () => ({ useScreenPublisher: vi.fn() }));

function Where() {
  return <p>at {useLocation().pathname}</p>;
}

describe("MindPage", () => {
  it("orders Beliefs, People, Entity search, Procedures", () => {
    render(<MemoryRouter><MindPage /></MemoryRouter>);
    const order = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    expect(order).toEqual(["Beliefs", "People", "Find an entity", "Procedures"]);
  });

  it("opens the chosen entity on its own page", () => {
    render(
      <MemoryRouter initialEntries={["/mind"]}>
        <Routes>
          <Route path="/mind" element={<MindPage />} />
          <Route path="/mind/:id" element={<Where />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "pick" }));
    expect(screen.getByText("at /mind/11111111-1111-4111-8111-111111111111")).toBeInTheDocument();
  });
});
