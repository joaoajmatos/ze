import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MindEntityPage } from "./MindEntityPage";

const { useEntityDetailQuery } = vi.hoisted(() => ({ useEntityDetailQuery: vi.fn() }));
vi.mock("@/entities/memory-graph", () => ({ useEntityDetailQuery }));
vi.mock("@/widgets/entity-neighbourhood", () => ({
  EntityNeighbourhood: ({ detail }: { detail: { entity: { canonical_name: string } } }) => <section aria-label="Neighbourhood">{detail.entity.canonical_name}</section>,
}));
vi.mock("@/widgets/entity-search", () => ({ EntitySearch: () => <section aria-label="Find an entity" /> }));
vi.mock("@/features/ask-bar", () => ({ useChatAbout: () => vi.fn() }));
vi.mock("@/entities/screen-context", () => ({ useScreenPublisher: vi.fn() }));

const UUID = "11111111-1111-4111-8111-111111111111";

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/mind/:entityId" element={<MindEntityPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MindEntityPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the entity detail and shows its neighbourhood", () => {
    useEntityDetailQuery.mockReturnValue({ data: { entity: { id: UUID, canonical_name: "Ada" } }, isLoading: false, isError: false });
    at(`/mind/${UUID}`);
    expect(useEntityDetailQuery).toHaveBeenCalledWith(UUID);
    expect(screen.getByRole("region", { name: "Neighbourhood" })).toHaveTextContent("Ada");
    expect(screen.getByRole("link", { name: /back to mind/i })).toHaveAttribute("href", "/mind");
  });

  it("says there is no entity here for a 404 and keeps the search", () => {
    useEntityDetailQuery.mockReturnValue({ data: null, isLoading: false, isError: false });
    at(`/mind/${UUID}`);
    expect(screen.getByText("No entity here")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Find an entity" })).toBeInTheDocument();
  });

  it("treats a non-UUID path as not found without calling the API", () => {
    useEntityDetailQuery.mockReturnValue({ data: undefined, isLoading: false, isError: false });
    at("/mind/graph-of-everything");
    expect(useEntityDetailQuery).toHaveBeenCalledWith(null);
    expect(screen.getByText("No entity here")).toBeInTheDocument();
  });

  it("shows an error with retry", () => {
    const refetch = vi.fn();
    useEntityDetailQuery.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch });
    at(`/mind/${UUID}`);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });
});
