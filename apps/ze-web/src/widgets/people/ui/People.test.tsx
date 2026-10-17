import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { People } from "./People";

const { useContactsPageQuery } = vi.hoisted(() => ({ useContactsPageQuery: vi.fn() }));
vi.mock("@/entities/contact", () => ({ useContactsPageQuery }));
vi.mock("@/features/primitive-tree", () => ({
  ConnectedPrimitiveTree: ({ components }: { components: unknown }) => <div data-testid="tree">{JSON.stringify(components)}</div>,
}));

describe("People", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the contacts tree inside the People module", () => {
    useContactsPageQuery.mockReturnValue({ data: { title: "Contacts", tree: [{ type: "text", text: "Ada" }] }, isLoading: false, isError: false });
    render(<People />);
    expect(screen.getByRole("region", { name: "People" })).toBeInTheDocument();
    expect(screen.getByTestId("tree")).toHaveTextContent("Ada");
  });

  it("shows loading", () => {
    useContactsPageQuery.mockReturnValue({ isLoading: true });
    render(<People />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error with retry", () => {
    const refetch = vi.fn();
    useContactsPageQuery.mockReturnValue({ isLoading: false, isError: true, refetch });
    render(<People />);
    screen.getByRole("button", { name: /retry/i }).click();
    expect(refetch).toHaveBeenCalled();
  });

  it("shows an empty state for an empty tree", () => {
    useContactsPageQuery.mockReturnValue({ data: { title: "Contacts", tree: [] }, isLoading: false, isError: false });
    render(<People />);
    expect(screen.getByText(/no people yet/i)).toBeInTheDocument();
  });
});
