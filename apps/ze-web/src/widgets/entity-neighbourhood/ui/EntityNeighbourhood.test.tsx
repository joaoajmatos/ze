import type { EntityDetailResponse, GraphEntityNode } from "@myguyze/ze-client";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EntityNeighbourhood } from "./EntityNeighbourhood";

const { useNarrow, mutate } = vi.hoisted(() => ({ useNarrow: vi.fn(), mutate: vi.fn() }));

vi.mock("@/shared/lib", async (orig) => ({ ...(await orig<typeof import("@/shared/lib")>()), useNarrow }));
vi.mock("@/entities/memory-feed-item", async (orig) => ({
  ...(await orig<typeof import("@/entities/memory-feed-item")>()),
  useReviewFactMutation: () => ({ mutate, isPending: false }),
}));
vi.mock("@myguyze/ze-ui/charts", () => ({
  LineChart: ({ title }: { title?: string }) => <div data-testid="activity-chart">{title}</div>,
}));

const node = (id: string, name: string): GraphEntityNode => ({ id, entity_type: "person", canonical_name: name, aliases: [], attrs: {}, degree: 2 });

const detail = (over: Partial<EntityDetailResponse> = {}): EntityDetailResponse => ({
  entity: node("c", "Ada"),
  facts: [
    {
      id: "f1",
      key: "works_at",
      value: "Acme",
      agent: "companion",
      created_at: "2026-10-01T08:00:00Z",
      claim_kind: "fact",
      confidence: 0.7,
      reviewed: false,
      contradicted: false,
      provenance: "raw",
    },
  ],
  episodes: [],
  neighbours: [node("a", "Bob"), node("b", "Cleo")],
  neighbour_total: 2,
  neighbour_edges: [
    { id: "e1", source_id: "c", target_id: "a", predicate: "works_with", confidence: 1 },
    { id: "e2", source_id: "c", target_id: "b", predicate: "knows", confidence: 1 },
  ],
  ...over,
});

describe("EntityNeighbourhood", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useNarrow.mockReturnValue(false);
  });

  it("draws the centre and focusable neighbour marks that open the entity", () => {
    const onSelect = vi.fn();
    render(<EntityNeighbourhood detail={detail()} onSelectEntity={onSelect} />);
    const mark = screen.getByRole("link", { name: /open bob, works with/i });
    fireEvent.keyDown(mark, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("a");
    expect(screen.getByRole("img", { name: /ada and 2 neighbours/i })).toBeInTheDocument();
  });

  it("caps the field and says how many more there are", () => {
    const ns = Array.from({ length: 20 }, (_, i) => node(`n${i}`, `N${i}`));
    render(<EntityNeighbourhood detail={detail({ neighbours: ns, neighbour_total: 27, neighbour_edges: [] })} onSelectEntity={vi.fn()} />);
    expect(screen.getAllByRole("link")).toHaveLength(20);
    expect(screen.getByText("+7 more")).toBeInTheDocument();
  });

  it("labels the activity line honestly", () => {
    render(<EntityNeighbourhood detail={detail({ episodes: [{ id: "x", agent: "companion", summary: "s", created_at: "2026-10-02T08:00:00Z" }] })} onSelectEntity={vi.fn()} />);
    expect(screen.getByTestId("activity-chart")).toHaveTextContent("last 20 facts and 10 episodes");
  });

  it("shows facts as belief rows with Keep, Drop and Edit", () => {
    render(<EntityNeighbourhood detail={detail()} onSelectEntity={vi.fn()} />);
    expect(screen.getByText("Works at Acme")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /keep this/i }));
    expect(mutate).toHaveBeenCalledWith({ actions: [{ id: "f1", action: "confirm" }] });
  });

  it("renders a grouped list instead of the field on a phone", () => {
    useNarrow.mockReturnValue(true);
    render(<EntityNeighbourhood detail={detail()} onSelectEntity={vi.fn()} />);
    expect(screen.queryByRole("img", { name: /neighbours/i })).toBeNull();
    const group = screen.getByRole("group", { name: "Works with" });
    fireEvent.click(within(group).getByRole("button", { name: "Bob" }));
  });

  it("chats about the centre, a neighbour mark and a fact with their refs", () => {
    const onChatAbout = vi.fn();
    render(<EntityNeighbourhood detail={detail()} onSelectEntity={vi.fn()} onChatAbout={onChatAbout} />);
    fireEvent.click(screen.getByRole("button", { name: "Chat about Ada" }));
    expect(onChatAbout).toHaveBeenLastCalledWith({ kind: "entity", id: "c", label: "Ada", component: "entity_module" }, expect.any(Element));
    fireEvent.keyDown(screen.getByRole("link", { name: /open bob/i }), { key: "c" });
    expect(onChatAbout).toHaveBeenLastCalledWith({ kind: "entity", id: "a", label: "Bob", component: "entity_module" }, expect.any(Element));
    fireEvent.click(screen.getByRole("button", { name: "Chat about this belief" }));
    expect(onChatAbout).toHaveBeenLastCalledWith({ kind: "fact", id: "f1", label: "Works at Acme", component: "belief_row" }, expect.any(Element));
  });

  it("says so when nothing is connected", () => {
    render(<EntityNeighbourhood detail={detail({ neighbours: [], neighbour_total: 0, neighbour_edges: [], facts: [] })} onSelectEntity={vi.fn()} />);
    expect(screen.getByText(/nothing connected to ada yet/i)).toBeInTheDocument();
  });
});
